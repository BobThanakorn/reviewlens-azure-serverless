import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from common import classifier as c
from common.config import ConfigError, Settings
from pipeline.enrich.prompt import FEW_SHOT_EXAMPLES, RETRY_NUDGE, SYSTEM_PROMPT, build_messages

GOOD = json.dumps(
    {"sentiment": "positive", "topic": "food", "summary": "อร่อยมาก"}, ensure_ascii=False
)


class Throttled(Exception):
    status_code = 429


def completion(content: str, tokens_in: int = 10, tokens_out: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out),
    )


def make_openai(*replies, **kwargs) -> tuple[c.OpenAIClassifier, MagicMock]:
    client = MagicMock()
    client.chat.completions.create.side_effect = list(replies)
    clf = c.OpenAIClassifier(
        client, "gpt-test", build_messages, RETRY_NUDGE, sleep=lambda _s: None, **kwargs
    )
    return clf, client


# ---- validation


def test_validate_accepts_fenced_json_and_truncates_summary():
    long_summary = "ก" * 300
    raw = (
        "```json\n"
        + json.dumps({"sentiment": "Negative", "topic": "price", "summary": long_summary})
        + "\n```"
    )
    sentiment, topic, summary = c.validate_output(raw)
    assert (sentiment, topic) == ("negative", "price")
    assert len(summary) == 120


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        json.dumps({"sentiment": "great", "topic": "food", "summary": "x"}),
        json.dumps({"sentiment": "positive", "topic": "parking", "summary": "x"}),
        json.dumps({"sentiment": "positive", "topic": "food"}),
        json.dumps({"sentiment": "positive", "topic": "food", "summary": "  "}),
    ],
)
def test_validate_rejects_bad_output(raw):
    with pytest.raises(c.InvalidOutputError):
        c.validate_output(raw)


# ---- OpenAI provider


def test_openai_valid_first_try_reports_tokens():
    clf, client = make_openai(completion(GOOD, 100, 20))
    result = clf.classify("อร่อย")
    assert (result.sentiment, result.topic, result.status) == ("positive", "food", "ok")
    assert (result.input_tokens, result.output_tokens) == (100, 20)
    assert result.provider == "openai" and result.model == "gpt-test"
    assert client.chat.completions.create.call_count == 1


def test_openai_invalid_then_valid_reasks_once_and_sums_tokens():
    clf, client = make_openai(completion("oops", 10, 2), completion(GOOD, 30, 4))
    result = clf.classify("อร่อย")
    assert result.status == "ok"
    assert (result.input_tokens, result.output_tokens) == (40, 6)
    second_messages = client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert second_messages[-1]["content"] == RETRY_NUDGE
    assert second_messages[-2] == {"role": "assistant", "content": "oops"}


def test_openai_invalid_twice_gives_unknown_invalid_output():
    clf, client = make_openai(completion("a"), completion("b"))
    result = clf.classify("x")
    assert (result.sentiment, result.topic, result.status) == (
        "unknown",
        "unknown",
        "invalid_output",
    )
    assert client.chat.completions.create.call_count == 2


def test_openai_request_uses_gpt5_compatible_parameters():
    clf, client = make_openai(completion(GOOD))
    clf.classify("x")
    kwargs = client.chat.completions.create.call_args.kwargs
    assert "temperature" not in kwargs and "max_tokens" not in kwargs  # gpt-5 rejects both
    assert kwargs["max_completion_tokens"] == c.MAX_COMPLETION_TOKENS
    assert "reasoning_effort" not in kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


def test_openai_reasoning_effort_is_sent_only_when_configured():
    clf, client = make_openai(completion(GOOD), reasoning_effort="minimal")
    clf.classify("x")
    assert client.chat.completions.create.call_args.kwargs["reasoning_effort"] == "minimal"


def test_openai_retries_429_then_succeeds():
    clf, client = make_openai(Throttled(), Throttled(), completion(GOOD))
    assert clf.classify("x").status == "ok"
    assert client.chat.completions.create.call_count == 3


def test_openai_gives_up_after_five_throttles():
    clf, client = make_openai(*[Throttled() for _ in range(5)])
    with pytest.raises(c.ClassifierError):
        clf.classify("x")
    assert client.chat.completions.create.call_count == 5


def test_non_throttle_errors_are_not_retried():
    clf, client = make_openai(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        clf.classify("x")
    assert client.chat.completions.create.call_count == 1


def test_backoff_delays_grow_exponentially_and_are_capped():
    delays: list[float] = []
    calls = {"n": 0}

    def always_throttled():
        calls["n"] += 1
        raise Throttled()

    with pytest.raises(c.ClassifierError):
        c.call_with_backoff(
            always_throttled, max_attempts=5, base_delay=1, max_delay=5,
            sleep=delays.append, jitter=lambda: 1.0,
        )  # fmt: skip
    assert calls["n"] == 5
    assert delays == [1, 2, 4, 5]


# ---- Language provider


def language_client(sentiment: str, is_error: bool = False):
    client = MagicMock()
    client.analyze_sentiment.return_value = [
        SimpleNamespace(sentiment=sentiment, is_error=is_error, error="bad")
    ]
    return client


@pytest.mark.parametrize(
    ("service_value", "expected"),
    [
        ("positive", "positive"),
        ("negative", "negative"),
        ("neutral", "neutral"),
        ("mixed", "neutral"),
    ],
)
def test_language_maps_sentiment(service_value, expected):
    clf = c.LanguageClassifier(language_client(service_value), sleep=lambda _s: None)
    assert clf.classify("ราคาแพงมาก").sentiment == expected


def test_language_topic_and_summary_rules():
    clf = c.LanguageClassifier(language_client("negative"))
    text = "ราคาแพงเกินไป " + "ก" * 200
    result = clf.classify(text)
    assert result.topic == "price"
    assert result.summary == text[:120]
    assert result.provider == "language"
    clf._client.analyze_sentiment.assert_called_once()
    assert clf._client.analyze_sentiment.call_args.kwargs["language"] == "th"


def test_language_service_error_raises():
    clf = c.LanguageClassifier(language_client("neutral", is_error=True))
    with pytest.raises(c.ClassifierError):
        clf.classify("x")


def test_language_unexpected_sentiment_raises():
    clf = c.LanguageClassifier(language_client("weird"))
    with pytest.raises(c.ClassifierError):
        clf.classify("x")


@pytest.mark.parametrize(
    ("text", "topic"),
    [
        ("ห้องน้ำสกปรกมาก มีแมลงสาบ", "cleanliness"),
        ("พนักงานบริการดี เสิร์ฟเร็ว", "service"),
        ("บรรยากาศดี ตกแต่งสวย เพลงเพราะ", "atmosphere"),
        ("ต้มยำรสชาติอร่อย", "food"),
        ("hello", "other"),
    ],
)
def test_keyword_topic(text, topic):
    assert c.keyword_topic(text) == topic


# ---- factory


def test_factory_rejects_openai_without_endpoint():
    with pytest.raises(ConfigError, match="openai_endpoint"):
        c.get_classifier(Settings(classifier_provider="openai"))


def test_factory_rejects_language_without_endpoint():
    with pytest.raises(ConfigError, match="language_endpoint"):
        c.get_classifier(Settings(classifier_provider="language"))


def test_settings_reject_unknown_provider():
    with pytest.raises(ConfigError):
        Settings.from_env({"CLASSIFIER_PROVIDER": "gemini"})


def test_settings_default_and_values():
    assert Settings.from_env({}).classifier_provider == "language"
    s = Settings.from_env(
        {
            "CLASSIFIER_PROVIDER": " OpenAI ",
            "OPENAI_ENDPOINT": "https://x",
            "OPENAI_REASONING_EFFORT": " Minimal ",
        }
    )
    assert (s.classifier_provider, s.openai_endpoint) == ("openai", "https://x")
    assert s.openai_reasoning_effort == "minimal"
    assert s.openai_api_version == "2025-04-01-preview"


# ---- prompt


def test_prompt_has_schema_and_three_original_examples():
    for key in ("sentiment", "topic", "summary", "120"):
        assert key in SYSTEM_PROMPT
    assert len(FEW_SHOT_EXAMPLES) == 3
    messages = build_messages("รีวิวทดสอบ")
    assert [m["role"] for m in messages] == ["system", *["user", "assistant"] * 3, "user"]
    assert messages[-1]["content"] == "รีวิวทดสอบ"
    for _text, answer in FEW_SHOT_EXAMPLES:
        assert len(answer["summary"]) <= 120
        c.validate_output(json.dumps(answer, ensure_ascii=False))
