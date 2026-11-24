"""Route table for the read-only API. Returns (status, JSON body); function_app adds HTTP."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from api import aggregate, validation
from common.logging_utils import log_event
from common.models import today_bangkok

logger = logging.getLogger("reviewlens.api")

ALL_DATA_DAYS = validation.MAX_DAYS


def cors_headers(origin: str | None, allowed_origin: str) -> dict[str, str]:
    """Allow exactly one origin (the static website). No wildcard."""
    if allowed_origin and origin == allowed_origin:
        return {
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Vary": "Origin",
        }
    return {"Vary": "Origin"}


def handle(
    store: Any, route: str, params: Mapping[str, str], now: datetime | None = None
) -> tuple[int, dict[str, Any]]:
    """Dispatch one GET request. ``route`` is the part after ``/api/`` (e.g. ``stats/daily``)."""
    today = today_bangkok(now or datetime.now(UTC))
    try:
        if route == "stats/daily":
            dates = aggregate.date_range(validation.parse_days(params), today)
            return 200, aggregate.daily_stats(aggregate.load_reviews(store, dates), dates)
        if route == "stats/topics":
            days = validation.parse_days(params, default=ALL_DATA_DAYS)
            dates = aggregate.date_range(days, today)
            return 200, aggregate.topic_stats(aggregate.load_reviews(store, dates))
        if route == "stats/accuracy":
            validation.parse_no_params(params)
            dates = aggregate.date_range(ALL_DATA_DAYS, today)
            return 200, aggregate.accuracy_stats(aggregate.load_reviews(store, dates))
        if route == "reviews":
            sentiment, limit = validation.parse_reviews_query(params)
            dates = aggregate.date_range(ALL_DATA_DAYS, today)
            reviews = aggregate.load_reviews(store, dates)
            return 200, aggregate.latest_reviews(reviews, sentiment, limit)
    except validation.ValidationError as exc:
        return 400, {"error": str(exc)}
    except Exception:
        logger.exception("api_unhandled_error")
        log_event(logger, "api_error", level=logging.ERROR, route=route)
        return 500, {"error": "internal error"}
    return 404, {"error": "not found"}
