import json
from datetime import UTC, date, datetime

import pytest

from pipeline.ingest import handler as ingest

NOW = datetime(2026, 11, 25, 1, 0, 3, tzinfo=UTC)
TODAY = date(2026, 11, 25)


def raw_names(store):
    return store.list_names("raw")


def test_daily_ingest_copies_first_chunk_and_stamps_ingested_at(seeded):
    result = ingest.run_daily(seeded, now=NOW)
    assert result.ingested == [{"chunk": 1, "dt": "2026-11-25"}]
    assert raw_names(seeded) == ["dt=2026-11-25/chunk-000001.jsonl"]
    lines = seeded.read_text("raw", raw_names(seeded)[0]).splitlines()
    assert all(json.loads(ln)["ingested_at"] == "2026-11-25T01:00:03Z" for ln in lines)
    assert "รีวิว 10" in lines[0]  # Thai kept unescaped
    state, _ = seeded.read_json_with_etag("state", "next_chunk.json")
    assert state["next_chunk"] == 2
    assert result.remaining == 2


def test_second_run_takes_next_chunk(seeded):
    ingest.run_daily(seeded, now=NOW)
    result = ingest.run_daily(seeded, now=NOW)
    assert result.ingested[0]["chunk"] == 2
    assert len(raw_names(seeded)) == 2


def test_backfill_dates_are_today_minus_n_plus_1_to_today(seeded):
    result = ingest.run_backfill(seeded, {"backfill_days": 3}, now=NOW)
    assert [(i["chunk"], i["dt"]) for i in result.ingested] == [
        (1, "2026-11-23"),
        (2, "2026-11-24"),
        (3, "2026-11-25"),
    ]
    assert result.remaining == 0


def test_backfill_stops_when_chunks_run_out(seeded):
    result = ingest.ingest_chunks(seeded, 5, today=TODAY, now=NOW)
    assert len(result.ingested) == 3
    assert result.remaining == 0
    assert result.conflict is False


def test_no_chunks_left_is_a_clean_noop(seeded):
    ingest.ingest_chunks(seeded, 3, today=TODAY, now=NOW)
    before = dict(seeded.blobs)
    result = ingest.run_daily(seeded, now=NOW)
    assert result.ingested == []
    assert result.remaining == 0
    assert seeded.blobs == before


def test_empty_source_is_a_noop(store):
    result = ingest.run_daily(store, now=NOW)
    assert result.ingested == [] and result.remaining == 0


def test_etag_conflict_stops_without_advancing(seeded):
    seeded.write_text("state", "next_chunk.json", json.dumps({"next_chunk": 1}))
    seeded.fail_next_state_write = True
    result = ingest.ingest_chunks(seeded, 3, today=TODAY, now=NOW)
    assert result.conflict is True
    assert result.ingested == []
    state, _ = seeded.read_json_with_etag("state", "next_chunk.json")
    assert state["next_chunk"] == 1
    assert result.remaining == 3


@pytest.mark.parametrize("body", [None, [], {}, {"backfill_days": "3"}, {"backfill_days": 3.5},
                                  {"backfill_days": True}, {"backfill_days": 0},
                                  {"backfill_days": 11}, {"backfill_days": -1}])  # fmt: skip
def test_backfill_rejects_bad_requests(seeded, body):
    with pytest.raises(ingest.BadRequestError):
        ingest.run_backfill(seeded, body, now=NOW)
    assert raw_names(seeded) == []


@pytest.mark.parametrize("days", [1, 10])
def test_backfill_accepts_bounds(days):
    assert ingest.parse_backfill_days({"backfill_days": days}) == days
