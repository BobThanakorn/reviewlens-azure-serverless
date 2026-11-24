"""Binding layer checks: thin wrappers, host.json settings, and the models/logging helpers."""

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from api import function_app as api_app
from common import logging_utils, models
from common.config import ConfigError, Settings
from conftest import FakeClassifier, make_chunk
from pipeline import function_app as pipe_app

ROOT = Path(__file__).resolve().parent.parent


def test_host_json_queue_settings_match_the_spec():
    queues = json.loads((ROOT / "src/pipeline/host.json").read_text())["extensions"]["queues"]
    assert queues["batchSize"] == 1
    assert queues["newBatchThreshold"] == 0
    assert queues["maxDequeueCount"] == 3
    assert queues["messageEncoding"] == "none"  # Event Grid writes plain JSON, not base64


# The SDK validates function names on every get_functions() call and rejects a second call on
# the same app, so each app is indexed exactly once here.
PIPELINE_FUNCTIONS = {f.get_function_name(): f for f in pipe_app.app.get_functions()}
API_FUNCTIONS = {f.get_function_name(): f for f in api_app.app.get_functions()}


def test_pipeline_registers_three_functions():
    assert set(PIPELINE_FUNCTIONS) == {"daily_ingest", "backfill", "enrich"}


def test_backfill_is_function_key_protected():
    trigger = PIPELINE_FUNCTIONS["backfill"].get_trigger()
    assert str(trigger.auth_level).upper().endswith("FUNCTION")
    assert [str(getattr(m, "value", m)) for m in trigger.methods] == ["POST"]


def test_api_is_get_only_and_anonymous():
    assert set(API_FUNCTIONS) == {"api"}
    trigger = API_FUNCTIONS["api"].get_trigger()
    assert sorted(str(getattr(m, "value", m)) for m in trigger.methods) == ["GET", "OPTIONS"]
    assert str(trigger.auth_level).upper().endswith("ANONYMOUS")


def test_enrich_reads_the_enrich_queue_with_identity_connection():
    trigger = PIPELINE_FUNCTIONS["enrich"].get_trigger()
    assert trigger.queue_name == "enrich"
    assert trigger.connection == "DataStorage"  # resolved via DataStorage__queueServiceUri


def test_timer_is_0100_utc_which_is_0800_bangkok():
    assert PIPELINE_FUNCTIONS["daily_ingest"].get_trigger().schedule == "0 0 1 * * *"


def test_backfill_request_paths(monkeypatch, seeded):
    monkeypatch.setattr(pipe_app, "get_store", lambda: seeded)
    status, body = pipe_app.backfill_request(b'{"backfill_days": 2}')
    assert status == 200 and len(body["ingested"]) == 2
    assert pipe_app.backfill_request(b"not json")[0] == 400
    assert pipe_app.backfill_request(b'{"backfill_days": 99}')[0] == 400
    assert pipe_app.backfill_request(b"")[0] == 400


def test_json_response_keeps_thai():
    resp = pipe_app.json_response(200, {"t": "ไทย"})
    assert "ไทย" in resp.get_body().decode()
    assert resp.mimetype == "application/json"


def test_api_respond_adds_cors_for_configured_origin(monkeypatch, store):
    monkeypatch.setattr(api_app, "get_store", lambda: store)
    monkeypatch.setenv("WEB_ORIGIN", "https://site.example")
    status, body, headers = api_app.respond("stats/accuracy", {}, "https://site.example")
    assert status == 200 and body["sample_size"] == 0
    assert headers["Access-Control-Allow-Origin"] == "https://site.example"
    resp = api_app.to_http(status, body, headers)
    assert resp.status_code == 200 and resp.headers["Vary"] == "Origin"


def test_enrich_wiring_uses_cached_classifier(monkeypatch, store):
    store.write_text("raw", "dt=2026-11-25/chunk-000001.jsonl", make_chunk(1))
    monkeypatch.setattr(pipe_app, "get_store", lambda: store)
    monkeypatch.setattr(pipe_app, "get_cached_classifier", lambda: FakeClassifier())
    msg = json.dumps(
        {"subject": "/blobServices/default/containers/raw/blobs/dt=2026-11-25/chunk-000001.jsonl"}
    )
    from pipeline.enrich.handler import handle_message

    assert (
        handle_message(pipe_app.get_store(), pipe_app.get_cached_classifier(), msg)["reviews"] == 3
    )


# ---- models / config / logging


@pytest.mark.parametrize(
    ("stars", "expected"),
    [(1, "negative"), (2, "negative"), (3, "neutral"), (4, "positive"), (5, "positive")],
)
def test_ground_truth_mapping(stars, expected):
    assert models.stars_to_sentiment(stars) == expected


def test_bangkok_date_rolls_over_at_17_utc():
    assert models.today_bangkok(datetime(2026, 11, 25, 16, 59, tzinfo=UTC)) == date(2026, 11, 25)
    assert models.today_bangkok(datetime(2026, 11, 25, 17, 0, tzinfo=UTC)) == date(2026, 11, 26)


def test_blob_name_helpers_round_trip():
    name = models.dated_blob_name("2026-11-25", 7)
    assert name == "dt=2026-11-25/chunk-000007.jsonl"
    assert models.parse_dated_blob_name(name) == ("2026-11-25", 7)
    assert models.source_blob_name(7) == "chunks/000007.jsonl"
    with pytest.raises(ValueError, match="unexpected"):
        models.parse_dated_blob_name("chunks/000007.jsonl")


def test_log_event_emits_json(caplog):
    with caplog.at_level(logging.INFO, logger="t"):
        logging_utils.log_event(logging.getLogger("t"), "hello", n=1, when=date(2026, 1, 2))
    assert json.loads(caplog.messages[0]) == {"event": "hello", "n": 1, "when": "2026-01-02"}


def test_settings_require_lists_missing():
    with pytest.raises(ConfigError, match="data_blob_url"):
        Settings().require("data_blob_url")
    Settings(data_blob_url="https://x").require("data_blob_url")
