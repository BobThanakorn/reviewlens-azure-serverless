import json
from datetime import UTC, date, datetime

import pytest

from api import aggregate, handler, validation

NOW = datetime(2026, 11, 25, 5, 0, 0, tzinfo=UTC)


def row(rid, stars, sentiment, topic="food", status="ok", processed_at="2026-11-25T02:00:00Z"):
    return {
        "review_id": rid, "review_text": f"ข้อความ {rid}", "stars": stars,
        "sentiment": sentiment, "topic": topic, "summary": "สรุป", "status": status,
        "provider": "fake", "model": "m", "input_tokens": 1, "output_tokens": 1,
        "processed_at": processed_at,
    }  # fmt: skip


def put(store, dt, rows, chunk=1):
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    store.write_text("processed", f"dt={dt}/chunk-{chunk:06d}.jsonl", body)


@pytest.fixture
def data(store):
    today_rows = [
        row(1, 5, "positive"),
        row(2, 1, "negative", "service"),
        row(3, 3, "neutral", "price"),
    ]
    yesterday_rows = [
        row(4, 2, "positive", "food"),
        row(5, 4, "unknown", "unknown", "invalid_output"),
    ]
    put(store, "2026-11-25", today_rows)
    put(store, "2026-11-24", yesterday_rows, chunk=2)
    return store


def test_daily_series_has_zero_filled_days(data):
    status, body = handler.handle(data, "stats/daily", {"days": "3"}, NOW)
    assert status == 200 and body["days"] == 3
    assert [d["date"] for d in body["series"]] == ["2026-11-23", "2026-11-24", "2026-11-25"]
    assert body["series"][0]["total"] == 0
    last = body["series"][2]
    assert (last["total"], last["positive"], last["negative"], last["neutral"]) == (3, 1, 1, 1)
    assert body["series"][1]["unknown"] == 1


def test_default_days_is_14(data):
    _, body = handler.handle(data, "stats/daily", {}, NOW)
    assert body["days"] == 14


def test_topics(data):
    _, body = handler.handle(data, "stats/topics", {}, NOW)
    by_topic = {t["topic"]: t for t in body["topics"]}
    assert by_topic["food"]["count"] == 2
    assert by_topic["service"] == {"topic": "service", "count": 1, "negative": 1}
    assert by_topic["unknown"]["count"] == 1


def test_accuracy_and_confusion_matrix(data):
    _, body = handler.handle(data, "stats/accuracy", {}, NOW)
    # truth: r1 positive->positive OK, r2 negative->negative OK, r3 neutral->neutral OK,
    #        r4 (2 stars) negative->positive WRONG, r5 positive->unknown WRONG
    assert body["sample_size"] == 5 and body["correct"] == 3 and body["accuracy"] == 0.6
    m = body["confusion_matrix"]
    assert m["positive"] == {"positive": 1, "neutral": 0, "negative": 0, "unknown": 1}
    assert m["negative"] == {"positive": 1, "neutral": 0, "negative": 1, "unknown": 0}
    assert m["neutral"]["neutral"] == 1
    assert sum(sum(r.values()) for r in m.values()) == 5
    assert body["labels"] == ["positive", "neutral", "negative", "unknown"]


def test_reviews_filter_limit_and_order(data):
    _, body = handler.handle(data, "reviews", {"sentiment": "negative", "limit": "5"}, NOW)
    assert [r["review_id"] for r in body["reviews"]] == [2]
    _, body = handler.handle(data, "reviews", {"limit": "2"}, NOW)
    assert [r["review_id"] for r in body["reviews"]] == [3, 2]  # newest date, highest id first
    assert set(body["reviews"][0]) == {
        "review_id", "review_text", "stars", "sentiment", "topic", "summary", "date",
    }  # fmt: skip


def test_duplicate_review_ids_use_latest_processing(store):
    put(store, "2026-11-25", [row(1, 5, "negative", processed_at="2026-11-25T01:00:00Z")])
    put(store, "2026-11-24", [row(1, 5, "positive", processed_at="2026-11-25T03:00:00Z")], chunk=2)
    reviews = aggregate.load_reviews(store, ["2026-11-24", "2026-11-25"])
    assert len(reviews) == 1 and reviews[0]["sentiment"] == "positive"


def test_empty_store_returns_200_with_zeros(store):
    assert handler.handle(store, "stats/accuracy", {}, NOW)[1]["accuracy"] == 0.0
    assert handler.handle(store, "reviews", {}, NOW)[1] == {"count": 0, "reviews": []}
    status, body = handler.handle(store, "stats/daily", {"days": "2"}, NOW)
    assert status == 200 and sum(d["total"] for d in body["series"]) == 0


@pytest.mark.parametrize(
    ("route", "params"),
    [
        ("stats/daily", {"days": "0"}),
        ("stats/daily", {"days": "31"}),
        ("stats/daily", {"days": "-1"}),
        ("stats/daily", {"days": "1.5"}),
        ("stats/daily", {"days": "๓"}),
        ("stats/daily", {"days": "abc"}),
        ("stats/daily", {"days": "3", "x": "1"}),
        ("stats/topics", {"days": "99"}),
        ("stats/accuracy", {"days": "3"}),
        ("reviews", {"sentiment": "angry"}),
        ("reviews", {"limit": "0"}),
        ("reviews", {"limit": "101"}),
        ("reviews", {"sentiment": "negative; drop"}),
        ("reviews", {"foo": "bar"}),
    ],
)
def test_bad_parameters_return_400(store, route, params):
    status, body = handler.handle(store, route, params, NOW)
    assert status == 400 and list(body) == ["error"]


def test_unknown_route_is_404(store):
    assert handler.handle(store, "stats/nope", {}, NOW) == (404, {"error": "not found"})


def test_unexpected_error_is_500_without_details(store):
    class Broken:
        def list_names(self, *_a, **_k):
            raise RuntimeError("secret internal detail")

    status, body = handler.handle(Broken(), "stats/topics", {}, NOW)
    assert status == 500 and body == {"error": "internal error"}


def test_cors_only_for_the_web_origin():
    web = "https://site.example"
    assert handler.cors_headers(web, web)["Access-Control-Allow-Origin"] == web
    assert "Access-Control-Allow-Origin" not in handler.cors_headers("https://evil.example", web)
    assert "Access-Control-Allow-Origin" not in handler.cors_headers(web, "")
    assert "*" not in handler.cors_headers(web, web).values()


def test_date_range_is_oldest_first():
    assert aggregate.date_range(3, date(2026, 11, 25)) == ["2026-11-23", "2026-11-24", "2026-11-25"]


def test_validation_defaults():
    assert validation.parse_days({}) == 14
    assert validation.parse_reviews_query({}) == (None, 20)
