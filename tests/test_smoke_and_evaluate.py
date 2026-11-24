from unittest.mock import MagicMock

import pytest

import evaluate
import smoke_test as st
from conftest import FakeStore

# ---------------------------------------------------------------- smoke_test


def test_wait_returns_when_enough_chunks_appear():
    counts = iter([0, 0, 3])
    assert st.wait_for_processed(lambda: next(counts), 3, interval_s=0, sleep=lambda _s: None) == 3


def test_wait_times_out():
    now = {"t": 0.0}

    def clock():
        return now["t"]

    def sleep(s):
        now["t"] += s

    with pytest.raises(st.SmokeTestError, match="timeout"):
        st.wait_for_processed(lambda: 0, 3, timeout_s=30, interval_s=10, sleep=sleep, clock=clock)


def good_fetch(url):
    if "stats/daily" in url:
        return {"days": 14, "series": [{"date": "2026-11-25", "total": 5}]}
    if "stats/accuracy" in url:
        return {"sample_size": 5, "accuracy": 0.6}
    return {"ok": True}


def test_check_api_accepts_valid_responses():
    results = st.check_api("https://api.example/api/", fetch=good_fetch)
    assert set(results) == set(st.API_ROUTES)


@pytest.mark.parametrize(
    "broken",
    [
        lambda url: [],
        lambda url: {},
        lambda url: {"sample_size": 0} if "accuracy" in url else good_fetch(url),
        lambda url: {"series": [{"total": 0}]} if "daily" in url else good_fetch(url),
    ],
)
def test_check_api_rejects_bad_responses(broken):
    with pytest.raises(st.SmokeTestError):
        st.check_api("https://api.example/api", fetch=broken)


def test_poison_queue_must_be_empty():
    queue = MagicMock()
    queue.peek_messages.return_value = []
    st.check_poison_queue(queue)
    queue.peek_messages.return_value = [object()]
    with pytest.raises(st.SmokeTestError, match="poison"):
        st.check_poison_queue(queue)


def test_http_json_refuses_plain_http():
    with pytest.raises(st.SmokeTestError, match="non-https"):
        st.http_json("http://insecure.example")


def test_dry_run_calls_nothing(capsys):
    assert st.main(["--dry-run", "--days", "3"]) == 0
    assert "dry-run" in capsys.readouterr().out


# ------------------------------------------------------------------ evaluate


def review(rid, stars, sentiment, topic="food", text="รีวิว", status="ok"):
    return {
        "review_id": rid, "review_text": text, "stars": stars, "sentiment": sentiment,
        "topic": topic, "summary": "สรุป", "status": status, "provider": "fake",
        "model": "m", "input_tokens": 10, "output_tokens": 2,
        "processed_at": "2026-11-25T02:00:00Z",
    }  # fmt: skip


SAMPLE = [
    review(1, 5, "positive"),
    review(2, 3, "positive", text="กลางๆ " * 100),  # neutral truth, predicted positive
    review(3, 1, "negative"),
    review(4, 4, "unknown", status="invalid_output"),
    review(5, 3, "neutral"),
]


def test_render_contains_real_numbers_and_matrix():
    md = evaluate.render(SAMPLE)
    assert "Sample size: **5**" in md
    assert "Accuracy: **60.0%**" in md
    assert "| neutral | 1 | 1 | 0 | 0 | 2 |" in md
    assert "Tokens used: 50 input, 10 output" in md
    assert "fake/m" in md


def test_examples_are_truncated_and_cover_distinct_cells():
    examples = evaluate.pick_examples(SAMPLE)
    assert [r["review_id"] for r in examples] == [2, 4]
    md = evaluate.render(SAMPLE)
    long_line = next(line for line in md.splitlines() if "กลางๆ" in line)
    assert len(long_line) <= evaluate.TEXT_LIMIT + 10
    assert long_line.rstrip().endswith("…")


def test_observations_mention_largest_error_and_invalid_rows():
    notes = "\n".join(evaluate.observations(evaluate.accuracy_stats(SAMPLE), SAMPLE))
    assert "**neutral** star rating were labelled **positive**" in notes
    assert "1 invalid-output" in notes


def test_analysis_is_embedded_only_when_given():
    assert "## Analysis" not in evaluate.render(SAMPLE)
    assert "## Analysis\n\nreasons" in evaluate.render(SAMPLE, analysis="reasons")


def test_main_writes_report_from_store(tmp_path):
    store = FakeStore()
    import json

    store.write_text(
        "processed", "dt=2026-11-25/chunk-000001.jsonl",
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in SAMPLE),
    )  # fmt: skip
    out = tmp_path / "evaluation.md"
    rc = evaluate.main(["--out", str(out), "--analysis", str(tmp_path / "none.md")], store=store)
    assert rc == 0 and "Accuracy" in out.read_text(encoding="utf-8")


def test_main_fails_cleanly_with_no_data(tmp_path, capsys):
    rc = evaluate.main(["--out", str(tmp_path / "x.md")], store=FakeStore())
    assert rc == 1 and "nothing to evaluate" in capsys.readouterr().err
