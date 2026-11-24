"""Review classifier behind one interface, with an OpenAI and an Azure AI Language provider."""

from __future__ import annotations

import json
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from common.config import ConfigError, Settings
from common.models import SENTIMENTS, SUMMARY_MAX_CHARS, TOPICS, UNKNOWN

T = TypeVar("T")

STATUS_OK = "ok"
STATUS_INVALID = "invalid_output"
LANGUAGE_TEXT_LIMIT = 5000  # Azure AI Language rejects records over 5,120 characters


@dataclass(frozen=True)
class Classification:
    sentiment: str
    topic: str
    summary: str
    provider: str
    model: str
    status: str = STATUS_OK
    input_tokens: int = 0
    output_tokens: int = 0


class Classifier(Protocol):
    provider: str
    model: str

    def classify(self, text: str) -> Classification: ...


class ClassifierError(Exception):
    """A single review could not be classified (e.g. throttled after all retries)."""


class InvalidOutputError(ValueError):
    """The model reply did not match the required schema."""


# ---------------------------------------------------------------- validation


def validate_output(raw: str) -> tuple[str, str, str]:
    """Parse and check a model reply. Returns (sentiment, topic, summary) or raises."""
    text = raw.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidOutputError(f"not JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise InvalidOutputError("JSON root is not an object")

    sentiment = str(data.get("sentiment", "")).strip().lower()
    topic = str(data.get("topic", "")).strip().lower()
    summary = data.get("summary")
    if sentiment not in SENTIMENTS:
        raise InvalidOutputError(f"bad sentiment: {sentiment!r}")
    if topic not in TOPICS:
        raise InvalidOutputError(f"bad topic: {topic!r}")
    if not isinstance(summary, str) or not summary.strip():
        raise InvalidOutputError("summary missing")
    return sentiment, topic, summary.strip()[:SUMMARY_MAX_CHARS]


# ------------------------------------------------------------------- backoff


def is_throttle(exc: BaseException) -> bool:
    return getattr(exc, "status_code", None) == 429


def call_with_backoff(
    fn: Callable[[], T],
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> T:
    """Retry ``fn`` on HTTP 429 with exponential backoff and full jitter."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_throttle(exc):
                raise
            if attempt == max_attempts:
                raise ClassifierError(f"throttled after {max_attempts} attempts") from exc
            sleep(jitter() * min(max_delay, base_delay * 2 ** (attempt - 1)))
    raise AssertionError("unreachable")  # pragma: no cover


# ------------------------------------------------------------------- OpenAI


class OpenAIClassifier:
    provider = "openai"

    def __init__(
        self,
        client: Any,
        deployment: str,
        build_messages: Callable[[str], list[dict[str, str]]],
        retry_nudge: str,
        max_attempts: int = 5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self.model = deployment
        self._build_messages = build_messages
        self._retry_nudge = retry_nudge
        self._max_attempts = max_attempts
        self._sleep = sleep

    def _complete(self, messages: list[dict[str, str]]) -> tuple[str, int, int]:
        def call():
            return self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_tokens=300,
                response_format={"type": "json_object"},
            )

        response = call_with_backoff(call, max_attempts=self._max_attempts, sleep=self._sleep)
        usage = getattr(response, "usage", None)
        return (
            response.choices[0].message.content or "",
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )

    def classify(self, text: str) -> Classification:
        messages = self._build_messages(text)
        tokens_in = tokens_out = 0
        for _ in range(2):  # first try, then one re-ask
            reply, used_in, used_out = self._complete(messages)
            tokens_in += used_in
            tokens_out += used_out
            try:
                sentiment, topic, summary = validate_output(reply)
            except InvalidOutputError:
                messages = [
                    *messages,
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": self._retry_nudge},
                ]
                continue
            return Classification(
                sentiment, topic, summary, self.provider, self.model,
                STATUS_OK, tokens_in, tokens_out,
            )  # fmt: skip
        return Classification(
            UNKNOWN, UNKNOWN, "", self.provider, self.model, STATUS_INVALID, tokens_in, tokens_out
        )


# ----------------------------------------------------------------- Language

# Checked in this order; the topic with the most keyword hits wins and ties go to the earlier
# entry. "food" comes last because food words appear in almost every review.
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cleanliness": ("สะอาด", "สกปรก", "ห้องน้ำ", "แมลง", "แมลงสาบ", "หนู", "เหม็น", "ความสะอาด"),
    "price": ("ราคา", "แพง", "ถูก", "คุ้ม", "บาท", "ส่วนลด", "โปรโมชั่น"),
    "service": ("บริการ", "พนักงาน", "เสิร์ฟ", "ต้อนรับ", "สุภาพ", "รอนาน", "ช้า", "เจ้าของร้าน"),
    "atmosphere": ("บรรยากาศ", "ตกแต่ง", "เพลง", "วิว", "นั่งสบาย", "แอร์", "ร้านสวย", "ที่นั่ง"),
    "food": ("อาหาร", "อร่อย", "รสชาติ", "เมนู", "เผ็ด", "หวาน", "เค็ม", "ก๋วยเตี๋ยว", "กาแฟ", "ข้าว"),
}  # fmt: skip


def keyword_topic(text: str) -> str:
    best, best_hits = "other", 0
    for topic, words in TOPIC_KEYWORDS.items():
        hits = sum(text.count(w) for w in words)
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


class LanguageClassifier:
    """Sentiment from Azure AI Language, topic from a keyword table, summary = first 120 chars."""

    provider = "language"
    model = "azure-ai-language"

    def __init__(
        self,
        client: Any,
        max_attempts: int = 5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._max_attempts = max_attempts
        self._sleep = sleep

    def classify(self, text: str) -> Classification:
        snippet = text[:LANGUAGE_TEXT_LIMIT]

        def call():
            return self._client.analyze_sentiment([snippet], language="th")[0]

        result = call_with_backoff(call, max_attempts=self._max_attempts, sleep=self._sleep)
        if getattr(result, "is_error", False):
            raise ClassifierError(f"language service error: {getattr(result, 'error', '')}")
        sentiment = "neutral" if result.sentiment == "mixed" else result.sentiment
        if sentiment not in SENTIMENTS:
            raise ClassifierError(f"unexpected sentiment: {result.sentiment!r}")
        return Classification(
            sentiment=sentiment,
            topic=keyword_topic(text),
            summary=text.strip()[:SUMMARY_MAX_CHARS],
            provider=self.provider,
            model=self.model,
        )


# ------------------------------------------------------------------- factory

_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


def get_classifier(settings: Settings) -> Classifier:
    """Build the provider chosen by CLASSIFIER_PROVIDER. Raises ConfigError if misconfigured."""
    if settings.classifier_provider == "openai":
        settings.require("openai_endpoint", "openai_deployment")
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        from pipeline.enrich.prompt import RETRY_NUDGE, build_messages

        client = AzureOpenAI(
            azure_endpoint=settings.openai_endpoint,
            api_version=settings.openai_api_version,
            azure_ad_token_provider=get_bearer_token_provider(
                DefaultAzureCredential(), _COGNITIVE_SCOPE
            ),
            max_retries=0,  # retries are handled by call_with_backoff
        )
        return OpenAIClassifier(
            client, settings.openai_deployment, build_messages, RETRY_NUDGE, settings.max_attempts
        )
    if settings.classifier_provider == "language":
        settings.require("language_endpoint")
        from azure.ai.textanalytics import TextAnalyticsClient
        from azure.identity import DefaultAzureCredential

        client = TextAnalyticsClient(settings.language_endpoint, DefaultAzureCredential())
        return LanguageClassifier(client, settings.max_attempts)
    raise ConfigError(f"unknown provider {settings.classifier_provider!r}")
