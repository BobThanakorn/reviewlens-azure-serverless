"""Ingest: simulate the daily arrival of reviews by copying source chunks into ``raw``."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from common.logging_utils import log_event
from common.models import (
    RAW_CONTAINER,
    SOURCE_CONTAINER,
    STATE_BLOB,
    STATE_CONTAINER,
    dated_blob_name,
    source_blob_name,
    today_bangkok,
)

logger = logging.getLogger("reviewlens.ingest")

MAX_BACKFILL_DAYS = 10


class BadRequestError(ValueError):
    """The admin request is invalid (maps to HTTP 400)."""


@dataclass
class IngestResult:
    ingested: list[dict[str, Any]] = field(default_factory=list)
    remaining: int = 0
    conflict: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"ingested": self.ingested, "remaining": self.remaining, "conflict": self.conflict}


def stamp_ingested_at(text: str, ingested_at: str) -> str:
    """Add ``ingested_at`` to every JSONL line, keeping Thai text unescaped."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        record["ingested_at"] = ingested_at
        out.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return "".join(out)


def ingest_chunks(
    store: Any, count: int, today: date | None = None, now: datetime | None = None
) -> IngestResult:
    """Ingest up to ``count`` chunks dated ``today-count+1 ... today``.

    The state blob is updated with an ETag condition after every chunk. If another writer
    changed it first (HTTP 412) we stop instead of ingesting a second copy.
    """
    now = now or datetime.now(UTC)
    today = today or today_bangkok(now)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    total = len(store.list_names(SOURCE_CONTAINER, "chunks/"))
    result = IngestResult()
    next_chunk = 1

    for offset in range(count):
        state, etag = store.read_json_with_etag(STATE_CONTAINER, STATE_BLOB)
        chunk = next_chunk = int(state["next_chunk"]) if state else 1
        if chunk > total or not store.exists(SOURCE_CONTAINER, source_blob_name(chunk)):
            log_event(logger, "ingest_no_more_chunks", next_chunk=chunk, total=total)
            break

        dt = today - timedelta(days=count - 1 - offset)
        text = store.read_text(SOURCE_CONTAINER, source_blob_name(chunk))
        store.write_text(RAW_CONTAINER, dated_blob_name(dt, chunk), stamp_ingested_at(text, stamp))

        new_state = {"next_chunk": chunk + 1, "updated_at": stamp}
        if not store.write_json_if_match(STATE_CONTAINER, STATE_BLOB, new_state, etag):
            log_event(logger, "ingest_state_conflict", level=logging.WARNING, chunk=chunk)
            result.conflict = True
            break
        next_chunk = chunk + 1
        result.ingested.append({"chunk": chunk, "dt": dt.isoformat()})
        log_event(logger, "ingest_chunk", chunk=chunk, dt=dt.isoformat())

    result.remaining = max(total - (next_chunk - 1), 0)
    return result


def parse_backfill_days(body: Any) -> int:
    """Validate ``{"backfill_days": N}`` with N an integer in 1..MAX_BACKFILL_DAYS."""
    if not isinstance(body, dict) or "backfill_days" not in body:
        raise BadRequestError('body must be {"backfill_days": N}')
    days = body["backfill_days"]
    if isinstance(days, bool) or not isinstance(days, int):
        raise BadRequestError("backfill_days must be an integer")
    if not 1 <= days <= MAX_BACKFILL_DAYS:
        raise BadRequestError(f"backfill_days must be between 1 and {MAX_BACKFILL_DAYS}")
    return days


def run_daily(store: Any, now: datetime | None = None) -> IngestResult:
    return ingest_chunks(store, 1, now=now)


def run_backfill(store: Any, body: Any, now: datetime | None = None) -> IngestResult:
    return ingest_chunks(store, parse_backfill_days(body), now=now)
