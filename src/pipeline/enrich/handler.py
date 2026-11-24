"""Enrich: classify every review of a raw chunk and write the processed chunk."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import Any

from common.classifier import Classifier, ClassifierError
from common.logging_utils import log_event
from common.models import PROCESSED_CONTAINER, RAW_CONTAINER, UNKNOWN, parse_dated_blob_name

logger = logging.getLogger("reviewlens.enrich")

STATUS_ERROR = "error"
_SUBJECT_RE = re.compile(
    r"^/blobServices/default/containers/(?P<container>[^/]+)/blobs/(?P<name>.+)$"
)


def parse_queue_message(body: str) -> tuple[str, bool] | None:
    """Return (raw blob name, force) for a message, or None when it must be ignored.

    Two shapes are accepted: an Event Grid BlobCreated event (normal path) and a manual
    ``{"blob": "dt=.../chunk-NNNNNN.jsonl", "force": true}`` used to reprocess a chunk.
    """
    data = json.loads(body)
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return None

    if "blob" in data:
        name, force = str(data["blob"]), bool(data.get("force", False))
    else:
        match = _SUBJECT_RE.match(str(data.get("subject", "")))
        if not match or match["container"] != RAW_CONTAINER:
            return None
        name, force = match["name"], False

    try:
        parse_dated_blob_name(name)
    except ValueError:
        return None
    return name, force


def error_record(review: dict[str, Any], provider: str, model: str, processed_at: str) -> dict:
    return {
        "review_id": review["review_id"],
        "review_text": review["review_text"],
        "stars": review["stars"],
        "sentiment": UNKNOWN,
        "topic": UNKNOWN,
        "summary": "",
        "status": STATUS_ERROR,
        "provider": provider,
        "model": model,
        "input_tokens": 0,
        "output_tokens": 0,
        "processed_at": processed_at,
    }


def process_chunk(
    store: Any,
    classifier: Classifier,
    blob_name: str,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify one raw chunk. The processed blob is written once at the end, so its
    existence means the chunk is complete and redelivered events can be skipped safely."""
    if not force and store.exists(PROCESSED_CONTAINER, blob_name):
        log_event(logger, "enrich_skipped_already_processed", blob=blob_name)
        return {"blob": blob_name, "skipped": True}

    started = time.perf_counter()
    lines = [ln for ln in store.read_text(RAW_CONTAINER, blob_name).splitlines() if ln.strip()]
    processed_at = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")

    out: list[str] = []
    counts = {"ok": 0, "invalid_output": 0, "error": 0}
    tokens_in = tokens_out = 0
    latency_ms: list[float] = []

    for line in lines:
        review = json.loads(line)
        t0 = time.perf_counter()
        try:
            result = classifier.classify(review["review_text"])
            record = {
                "review_id": review["review_id"],
                "review_text": review["review_text"],
                "stars": review["stars"],
                "sentiment": result.sentiment,
                "topic": result.topic,
                "summary": result.summary,
                "status": result.status,
                "provider": result.provider,
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "processed_at": processed_at,
            }
        except ClassifierError as exc:
            log_event(
                logger, "enrich_review_failed", level=logging.WARNING,
                review_id=review["review_id"], error=str(exc),
            )  # fmt: skip
            record = error_record(review, classifier.provider, classifier.model, processed_at)
        latency_ms.append((time.perf_counter() - t0) * 1000)
        counts[record["status"] if record["status"] in counts else "error"] += 1
        tokens_in += record["input_tokens"]
        tokens_out += record["output_tokens"]
        out.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    store.write_text(PROCESSED_CONTAINER, blob_name, "".join(out))

    summary = {
        "blob": blob_name,
        "skipped": False,
        "reviews": len(lines),
        "ok": counts["ok"],
        "invalid_output": counts["invalid_output"],
        "failures": counts["error"],
        "avg_latency_ms": round(sum(latency_ms) / len(latency_ms), 1) if latency_ms else 0.0,
        "total_ms": round((time.perf_counter() - started) * 1000, 1),
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "provider": classifier.provider,
    }
    log_event(logger, "enrich_chunk_done", **summary)
    return summary


def handle_message(
    store: Any, classifier: Classifier, body: str, now: datetime | None = None
) -> dict[str, Any] | None:
    parsed = parse_queue_message(body)
    if parsed is None:
        log_event(logger, "enrich_message_ignored", level=logging.WARNING)
        return None
    name, force = parsed
    return process_chunk(store, classifier, name, force=force, now=now)
