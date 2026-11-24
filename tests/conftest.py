"""Shared fixtures: an in-memory stand-in for BlobStore, so no Azure is needed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parent.parent / "sample-data" / "sample.jsonl"


class FakeStore:
    """Implements the BlobStore methods used by the app, with ETag semantics."""

    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], str] = {}
        self.etags: dict[tuple[str, str], int] = {}
        self.fail_next_state_write = False

    def exists(self, container, name):
        return (container, name) in self.blobs

    def read_text(self, container, name):
        return self.blobs[(container, name)]

    def write_text(self, container, name, text, overwrite=True):
        key = (container, name)
        if key in self.blobs and not overwrite:
            return False
        self.blobs[key] = text
        self.etags[key] = self.etags.get(key, 0) + 1
        return True

    def list_names(self, container, prefix=""):
        return sorted(n for (c, n) in self.blobs if c == container and n.startswith(prefix))

    def read_json_with_etag(self, container, name):
        key = (container, name)
        if key not in self.blobs:
            return None, None
        return json.loads(self.blobs[key]), str(self.etags[key])

    def write_json_if_match(self, container, name, data, etag):
        key = (container, name)
        if self.fail_next_state_write:
            self.fail_next_state_write = False
            return False
        current = str(self.etags[key]) if key in self.blobs else None
        if current != etag:
            return False
        self.write_text(container, name, json.dumps(data))
        return True


class FakeClassifier:
    provider = "fake"
    model = "fake-model"

    def __init__(self, behaviour=None) -> None:
        from common.classifier import Classification

        self._cls = Classification
        self.behaviour = behaviour
        self.calls: list[str] = []

    def classify(self, text):
        self.calls.append(text)
        if self.behaviour:
            return self.behaviour(text)
        sentiment = "negative" if "แย่" in text else "positive"
        return self._cls(sentiment, "food", text[:20], "fake", "fake-model", "ok", 10, 4)


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def classifier() -> FakeClassifier:
    return FakeClassifier()


def make_chunk(first_id: int, n: int = 3, stars: int = 5) -> str:
    return "".join(
        json.dumps(
            {"review_id": first_id + i, "review_text": f"รีวิว {first_id + i}", "stars": stars},
            ensure_ascii=False,
        )
        + "\n"
        for i in range(n)
    )


@pytest.fixture
def seeded(store: FakeStore) -> FakeStore:
    """Three source chunks of 3 reviews each."""
    for chunk in (1, 2, 3):
        store.write_text("source", f"chunks/{chunk:06d}.jsonl", make_chunk(chunk * 10))
    return store
