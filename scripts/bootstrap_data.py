"""Sample the Wongnai reviews dataset and upload it as JSONL chunks.

Steps: download train split -> drop empty reviews -> sample 500 rows (seed 42) ->
assign review_id -> split into chunks of 50 -> write to disk (--out-dir) or
upload to container ``source`` (blobs ``chunks/000001.jsonl`` ...) using Entra auth.

Re-running produces byte-identical output, so the upload is idempotent.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

DATASET_ID = "Wongnai/wongnai_reviews"
SAMPLE_SIZE = 500
CHUNK_SIZE = 50
SEED = 42
TEST_SAMPLE_SIZE = 20
SOURCE_CONTAINER = "source"
ROOT = Path(__file__).resolve().parent.parent

Review = dict[str, object]


def clean_rows(rows: Iterable[dict]) -> list[dict]:
    """Keep rows with non-empty text and a star rating in 1..5."""
    kept: list[dict] = []
    for row in rows:
        text = (row.get("review_body") or "").strip()
        stars = row.get("star_rating")
        if text and isinstance(stars, int) and 1 <= stars <= 5:
            kept.append({"review_text": text, "stars": stars})
    return kept


def sample_reviews(rows: list[dict], size: int = SAMPLE_SIZE, seed: int = SEED) -> list[Review]:
    """Deterministic random sample; review_id is the 1-based position in the sample."""
    if len(rows) < size:
        raise ValueError(f"need at least {size} usable rows, got {len(rows)}")
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling, not security related
    picked = rng.sample(range(len(rows)), size)
    return [
        {"review_id": i, "review_text": rows[idx]["review_text"], "stars": rows[idx]["stars"]}
        for i, idx in enumerate(picked, start=1)
    ]


def chunk_reviews(reviews: list[Review], size: int = CHUNK_SIZE) -> list[list[Review]]:
    return [reviews[i : i + size] for i in range(0, len(reviews), size)]


def chunk_blob_name(number: int) -> str:
    return f"chunks/{number:06d}.jsonl"


def to_jsonl(reviews: Iterable[Review]) -> str:
    """One JSON object per line, Thai text kept readable, trailing newline."""
    return "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in reviews)


def build_payloads(reviews: list[Review], chunk_size: int = CHUNK_SIZE) -> dict[str, str]:
    return {
        chunk_blob_name(n): to_jsonl(chunk)
        for n, chunk in enumerate(chunk_reviews(reviews, chunk_size), start=1)
    }


def write_local(payloads: dict[str, str], out_dir: Path) -> list[Path]:
    written = []
    for name, body in payloads.items():
        path = out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
        written.append(path)
    return written


def write_test_sample(reviews: list[Review], path: Path, size: int = TEST_SAMPLE_SIZE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_jsonl(reviews[:size]), encoding="utf-8", newline="\n")


def upload(payloads: dict[str, str], account_url: str, container_client=None) -> int:
    """Upload every payload with overwrite=True. ``container_client`` is injectable for tests."""
    if container_client is None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        service = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        container_client = service.get_container_client(SOURCE_CONTAINER)
    for name, body in payloads.items():
        container_client.upload_blob(name, body.encode("utf-8"), overwrite=True)
    return len(payloads)


def load_wongnai_train() -> list[dict]:
    """Download the train split. Imported lazily because ``datasets`` is a dev-only dependency."""
    from datasets import load_dataset

    dataset = load_dataset(DATASET_ID, split="train")
    label = dataset.features["star_rating"]

    def to_stars(value: int) -> int:
        # ClassLabel stores 0..4 and its names are "1".."5"; plain ints are used as they are.
        return int(label.int2str(value)) if hasattr(label, "int2str") else int(value)

    return [
        {"review_body": r["review_body"], "star_rating": to_stars(r["star_rating"])}
        for r in dataset
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", type=Path, help="write chunks here instead of uploading")
    p.add_argument(
        "--account-url",
        default=os.environ.get("REVIEWLENS_DATA_ACCOUNT_URL"),
        help="https://<account>.blob.core.windows.net (or env REVIEWLENS_DATA_ACCOUNT_URL)",
    )
    p.add_argument(
        "--sample-out",
        type=Path,
        default=ROOT / "sample-data" / "sample.jsonl",
        help="where to write the 20-row test sample",
    )
    p.add_argument("--no-sample", action="store_true", help="do not rewrite the test sample")
    return p.parse_args(argv)


def main(
    argv: list[str] | None = None, loader: Callable[[], list[dict]] = load_wongnai_train
) -> int:
    args = parse_args(argv)
    if args.out_dir is None and not args.account_url:
        print("error: pass --out-dir (dry run) or --account-url / REVIEWLENS_DATA_ACCOUNT_URL")
        return 2

    reviews = sample_reviews(clean_rows(loader()))
    payloads = build_payloads(reviews)
    print(f"sampled {len(reviews)} reviews into {len(payloads)} chunks")

    if not args.no_sample:
        write_test_sample(reviews, args.sample_out)
        print(f"wrote test sample: {args.sample_out}")

    if args.out_dir is not None:
        files = write_local(payloads, args.out_dir)
        print(f"dry run: wrote {len(files)} files under {args.out_dir}")
    else:
        count = upload(payloads, args.account_url)
        print(f"uploaded {count} blobs to container '{SOURCE_CONTAINER}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
