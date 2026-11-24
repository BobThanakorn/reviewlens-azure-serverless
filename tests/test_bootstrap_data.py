import json
from unittest.mock import MagicMock

import pytest

import bootstrap_data as bd


def fake_rows(n: int = 600) -> list[dict]:
    rows = [{"review_body": f"รีวิวที่ {i}", "star_rating": (i % 5) + 1} for i in range(n)]
    rows += [
        {"review_body": "", "star_rating": 3},
        {"review_body": "   ", "star_rating": 3},
        {"review_body": None, "star_rating": 4},
        {"review_body": "ดาวผิด", "star_rating": 9},
    ]
    return rows


def test_clean_rows_drops_empty_and_invalid():
    cleaned = bd.clean_rows(fake_rows(10))
    assert len(cleaned) == 10
    assert all(r["review_text"].strip() for r in cleaned)
    assert all(1 <= r["stars"] <= 5 for r in cleaned)


def test_sample_is_deterministic_and_ids_are_sequential():
    rows = bd.clean_rows(fake_rows())
    first = bd.sample_reviews(rows)
    second = bd.sample_reviews(rows)
    assert first == second
    assert len(first) == bd.SAMPLE_SIZE
    assert [r["review_id"] for r in first] == list(range(1, bd.SAMPLE_SIZE + 1))
    assert len({r["review_text"] for r in first}) == bd.SAMPLE_SIZE


def test_sample_needs_enough_rows():
    with pytest.raises(ValueError, match="at least"):
        bd.sample_reviews(bd.clean_rows(fake_rows(10)))


def test_chunks_are_50_rows_and_named_with_six_digits():
    reviews = bd.sample_reviews(bd.clean_rows(fake_rows()))
    payloads = bd.build_payloads(reviews)
    assert list(payloads) == [f"chunks/{n:06d}.jsonl" for n in range(1, 11)]
    for body in payloads.values():
        assert len(body.splitlines()) == bd.CHUNK_SIZE


def test_jsonl_keeps_thai_text_and_schema():
    body = bd.to_jsonl([{"review_id": 1, "review_text": "อร่อยมาก", "stars": 5}])
    assert "อร่อยมาก" in body
    assert body.endswith("\n")
    assert json.loads(body) == {"review_id": 1, "review_text": "อร่อยมาก", "stars": 5}


def test_main_dry_run_is_idempotent_and_writes_sample(tmp_path):
    out = tmp_path / "chunks"
    sample = tmp_path / "sample.jsonl"
    argv = ["--out-dir", str(out), "--sample-out", str(sample)]

    assert bd.main(argv, loader=fake_rows) == 0
    first = {p.name: p.read_bytes() for p in out.rglob("*.jsonl")}
    assert bd.main(argv, loader=fake_rows) == 0
    second = {p.name: p.read_bytes() for p in out.rglob("*.jsonl")}

    assert len(first) == 10
    assert first == second
    assert len(sample.read_text(encoding="utf-8").splitlines()) == bd.TEST_SAMPLE_SIZE


def test_main_requires_target(monkeypatch):
    monkeypatch.delenv("REVIEWLENS_DATA_ACCOUNT_URL", raising=False)
    assert bd.main(["--no-sample"], loader=fake_rows) == 2


def test_upload_overwrites_every_blob():
    container = MagicMock()
    payloads = {"chunks/000001.jsonl": "a\n", "chunks/000002.jsonl": "b\n"}
    count = bd.upload(payloads, "https://example.invalid", container_client=container)
    assert count == 2
    for call in container.upload_blob.call_args_list:
        assert call.kwargs["overwrite"] is True
    assert container.upload_blob.call_args_list[0].args[0] == "chunks/000001.jsonl"
