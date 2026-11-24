"""Read processed blobs and aggregate them in Python (the data set is small by design)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from typing import Any

from common.models import PROCESSED_CONTAINER, SENTIMENTS, TOPICS, UNKNOWN, stars_to_sentiment

PREDICTED_LABELS = (*SENTIMENTS, UNKNOWN)
DAILY_COLUMNS = (*SENTIMENTS, UNKNOWN)


def date_range(days: int, today: date) -> list[str]:
    """ISO dates oldest first, ending today."""
    return [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]


def load_reviews(store: Any, dates: list[str]) -> list[dict[str, Any]]:
    """Load processed reviews for the given dates, de-duplicated by review_id.

    A review can appear twice if a chunk was ingested again after a crash; the most recently
    processed copy wins.
    """
    latest: dict[int, dict[str, Any]] = {}
    for dt in dates:
        for name in store.list_names(PROCESSED_CONTAINER, f"dt={dt}/"):
            for line in store.read_text(PROCESSED_CONTAINER, name).splitlines():
                if not line.strip():
                    continue
                review = json.loads(line)
                review["date"] = dt
                current = latest.get(review["review_id"])
                if current is None or review["processed_at"] >= current["processed_at"]:
                    latest[review["review_id"]] = review
    return list(latest.values())


def daily_stats(reviews: list[dict[str, Any]], dates: list[str]) -> dict[str, Any]:
    by_day = {dt: Counter() for dt in dates}
    for r in reviews:
        if r["date"] in by_day:
            by_day[r["date"]][r["sentiment"]] += 1
    series = []
    for dt in dates:
        counts = by_day[dt]
        row: dict[str, Any] = {"date": dt, "total": sum(counts.values())}
        for label in DAILY_COLUMNS:
            row[label] = counts[label]
        series.append(row)
    return {"days": len(dates), "series": series}


def topic_stats(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    count: Counter[str] = Counter()
    negative: Counter[str] = Counter()
    for r in reviews:
        count[r["topic"]] += 1
        if r["sentiment"] == "negative":
            negative[r["topic"]] += 1
    topics = [{"topic": t, "count": count[t], "negative": negative[t]} for t in (*TOPICS, UNKNOWN)]
    return {"topics": topics}


def accuracy_stats(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare sentiment with the star-derived ground truth. ``unknown`` counts as wrong."""
    matrix = {t: dict.fromkeys(PREDICTED_LABELS, 0) for t in SENTIMENTS}
    correct = 0
    for r in reviews:
        truth = stars_to_sentiment(int(r["stars"]))
        predicted = r["sentiment"] if r["sentiment"] in PREDICTED_LABELS else UNKNOWN
        matrix[truth][predicted] += 1
        correct += truth == predicted
    size = len(reviews)
    return {
        "sample_size": size,
        "correct": correct,
        "accuracy": round(correct / size, 4) if size else 0.0,
        "labels": list(PREDICTED_LABELS),
        "confusion_matrix": matrix,
    }


def latest_reviews(
    reviews: list[dict[str, Any]], sentiment: str | None, limit: int
) -> dict[str, Any]:
    chosen = [r for r in reviews if sentiment is None or r["sentiment"] == sentiment]
    chosen.sort(key=lambda r: (r["date"], r["review_id"]), reverse=True)
    fields = ("review_id", "review_text", "stars", "sentiment", "topic", "summary", "date")
    items = [{k: r[k] for k in fields} for r in chosen[:limit]]
    return {"count": len(items), "reviews": items}
