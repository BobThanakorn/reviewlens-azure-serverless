"""Strict whitelist validation for query parameters. Anything unexpected is rejected."""

from __future__ import annotations

from collections.abc import Mapping

from common.models import SENTIMENTS, UNKNOWN

MAX_DAYS = 30
DEFAULT_DAYS = 14
MAX_LIMIT = 100
DEFAULT_LIMIT = 20
SENTIMENT_FILTERS = (*SENTIMENTS, UNKNOWN)


class ValidationError(ValueError):
    """Invalid request parameter (maps to HTTP 400)."""


def _reject_unknown(params: Mapping[str, str], allowed: set[str]) -> None:
    extra = sorted(set(params) - allowed)
    if extra:
        raise ValidationError(f"unknown parameter: {', '.join(extra)}")


def _int_in_range(raw: str, name: str, low: int, high: int) -> int:
    # isdecimal() rejects signs, spaces and unicode digits such as Thai numerals.
    if not (raw.isascii() and raw.isdecimal()):
        raise ValidationError(f"{name} must be an integer between {low} and {high}")
    value = int(raw)
    if not low <= value <= high:
        raise ValidationError(f"{name} must be an integer between {low} and {high}")
    return value


def parse_days(params: Mapping[str, str], default: int = DEFAULT_DAYS) -> int:
    _reject_unknown(params, {"days"})
    return _int_in_range(params["days"], "days", 1, MAX_DAYS) if "days" in params else default


def parse_no_params(params: Mapping[str, str]) -> None:
    _reject_unknown(params, set())


def parse_reviews_query(params: Mapping[str, str]) -> tuple[str | None, int]:
    _reject_unknown(params, {"sentiment", "limit"})
    sentiment = params.get("sentiment")
    if sentiment is not None and sentiment not in SENTIMENT_FILTERS:
        raise ValidationError(f"sentiment must be one of {', '.join(SENTIMENT_FILTERS)}")
    limit = (
        _int_in_range(params["limit"], "limit", 1, MAX_LIMIT)
        if "limit" in params
        else DEFAULT_LIMIT
    )
    return sentiment, limit
