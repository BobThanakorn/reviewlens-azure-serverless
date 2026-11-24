import json
from datetime import UTC, datetime

import pytest

from common.classifier import Classification, ClassifierError
from conftest import FakeClassifier, make_chunk
from pipeline.enrich import handler as enrich

NOW = datetime(2026, 11, 25, 2, 0, 0, tzinfo=UTC)
BLOB = "dt=2026-11-25/chunk-000001.jsonl"


def event(subject: str) -> str:
    return json.dumps({"eventType": "Microsoft.Storage.BlobCreated", "subject": subject})


GOOD_SUBJECT = f"/blobServices/default/containers/raw/blobs/{BLOB}"


@pytest.fixture
def with_raw(store):
    store.write_text("raw", BLOB, make_chunk(1, n=3, stars=5))
    return store


def processed(store):
    return [json.loads(ln) for ln in store.read_text("processed", BLOB).splitlines()]


def test_parse_event_extracts_blob_name():
    assert enrich.parse_queue_message(event(GOOD_SUBJECT)) == (BLOB, False)


def test_parse_manual_message_supports_force():
    assert enrich.parse_queue_message(json.dumps({"blob": BLOB, "force": True})) == (BLOB, True)


@pytest.mark.parametrize(
    "body",
    [
        event("/blobServices/default/containers/processed/blobs/" + BLOB),
        event("/blobServices/default/containers/raw/blobs/readme.txt"),
        event("nonsense"),
        json.dumps([]),
        json.dumps("text"),
    ],
)
def test_parse_ignores_foreign_messages(body):
    assert enrich.parse_queue_message(body) is None


def test_parse_accepts_event_list():
    assert enrich.parse_queue_message(json.dumps([json.loads(event(GOOD_SUBJECT))])) == (
        BLOB,
        False,
    )


def test_process_chunk_writes_all_fields_same_name(with_raw, classifier):
    summary = enrich.process_chunk(with_raw, classifier, BLOB, now=NOW)
    rows = processed(with_raw)
    assert len(rows) == 3 and summary["reviews"] == 3 and summary["ok"] == 3
    assert set(rows[0]) == {
        "review_id", "review_text", "stars", "sentiment", "topic", "summary", "status",
        "provider", "model", "input_tokens", "output_tokens", "processed_at",
    }  # fmt: skip
    assert rows[0]["processed_at"] == "2026-11-25T02:00:00Z"
    assert summary["input_tokens"] == 30 and summary["output_tokens"] == 12


def test_second_delivery_is_skipped_without_calling_classifier(with_raw, classifier):
    enrich.process_chunk(with_raw, classifier, BLOB, now=NOW)
    calls = len(classifier.calls)
    again = enrich.process_chunk(with_raw, classifier, BLOB, now=NOW)
    assert again == {"blob": BLOB, "skipped": True}
    assert len(classifier.calls) == calls


def test_force_reprocesses(with_raw, classifier):
    enrich.process_chunk(with_raw, classifier, BLOB, now=NOW)
    enrich.process_chunk(with_raw, classifier, BLOB, force=True, now=NOW)
    assert len(classifier.calls) == 6


def test_invalid_output_is_recorded_not_dropped(with_raw):
    clf = FakeClassifier(
        lambda t: Classification("unknown", "unknown", "", "fake", "m", "invalid_output", 5, 1)
    )
    summary = enrich.process_chunk(with_raw, clf, BLOB, now=NOW)
    assert summary["invalid_output"] == 3
    assert {r["status"] for r in processed(with_raw)} == {"invalid_output"}


def test_throttled_review_becomes_error_row_and_chunk_is_still_written(with_raw):
    def behave(text):
        if "2" in text:
            raise ClassifierError("throttled after 5 attempts")
        return Classification("positive", "food", "ok", "fake", "m", "ok", 1, 1)

    summary = enrich.process_chunk(with_raw, FakeClassifier(behave), BLOB, now=NOW)
    rows = processed(with_raw)
    assert summary["failures"] == 1 and summary["ok"] == 2
    bad = next(r for r in rows if r["review_id"] == 2)
    assert (bad["status"], bad["sentiment"], bad["topic"]) == ("error", "unknown", "unknown")


def test_unexpected_exception_propagates_and_writes_nothing(with_raw):
    def boom(_text):
        raise RuntimeError("auth failure")

    with pytest.raises(RuntimeError):
        enrich.process_chunk(with_raw, FakeClassifier(boom), BLOB, now=NOW)
    assert not with_raw.exists("processed", BLOB)


def test_handle_message_end_to_end_and_ignore(with_raw, classifier):
    out = enrich.handle_message(with_raw, classifier, event(GOOD_SUBJECT), now=NOW)
    assert out["reviews"] == 3
    assert enrich.handle_message(with_raw, classifier, event("garbage"), now=NOW) is None
