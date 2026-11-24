"""Shared constants and small helpers used by the pipeline and the API."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta, timezone

SENTIMENTS = ("positive", "neutral", "negative")
TOPICS = ("food", "service", "price", "atmosphere", "cleanliness", "other")
UNKNOWN = "unknown"
SUMMARY_MAX_CHARS = 120

RAW_CONTAINER = "raw"
PROCESSED_CONTAINER = "processed"
SOURCE_CONTAINER = "source"
STATE_CONTAINER = "state"
STATE_BLOB = "next_chunk.json"

BANGKOK = timezone(timedelta(hours=7), "Asia/Bangkok")

_CHUNK_RE = re.compile(r"^dt=(\d{4}-\d{2}-\d{2})/chunk-(\d{6})\.jsonl$")


def stars_to_sentiment(stars: int) -> str:
    """Ground truth used for accuracy: 1-2 negative, 3 neutral, 4-5 positive."""
    if stars <= 2:
        return "negative"
    if stars == 3:
        return "neutral"
    return "positive"


def today_bangkok(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(BANGKOK).date()


def source_blob_name(chunk: int) -> str:
    return f"chunks/{chunk:06d}.jsonl"


def dated_blob_name(dt: date | str, chunk: int) -> str:
    return f"dt={dt}/chunk-{chunk:06d}.jsonl"


def parse_dated_blob_name(name: str) -> tuple[str, int]:
    """Return (date string, chunk number) for ``dt=YYYY-MM-DD/chunk-NNNNNN.jsonl``."""
    match = _CHUNK_RE.match(name)
    if not match:
        raise ValueError(f"unexpected blob name: {name!r}")
    return match.group(1), int(match.group(2))
