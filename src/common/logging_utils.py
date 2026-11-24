"""Structured JSON logging so Log Analytics can query fields directly."""

from __future__ import annotations

import json
import logging
from typing import Any


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Emit one JSON line: {"event": ..., <fields>}. Non-serialisable values become strings."""
    logger.log(level, json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))
