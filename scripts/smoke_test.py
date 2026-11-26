"""End-to-end smoke test of a deployed environment.

1. POST /api/ops/backfill {"backfill_days": N} on func-pipeline (function key).
2. Poll until N new processed blobs exist (max 10 minutes).
3. GET every API route and assert valid, non-empty JSON.
4. Assert the poison queue is empty.
5. Print the dashboard URL.

Auth: Entra (DefaultAzureCredential) for blobs and queues, ``az functionapp keys list`` for the
admin key. No secret is read from or written to a file.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TF_ENV_DIR = ROOT / "terraform" / "envs" / "dev"
POLL_TIMEOUT_S = 600
POLL_INTERVAL_S = 15
API_ROUTES = (
    "stats/daily?days=14",
    "stats/topics",
    "stats/accuracy",
    "reviews?sentiment=negative&limit=20",
)


class SmokeTestError(RuntimeError):
    pass


def http_json(
    url: str, method: str = "GET", body: dict | None = None, headers: dict | None = None
) -> Any:
    if not url.startswith("https://"):
        raise SmokeTestError(f"refusing non-https url: {url}")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )  # fmt: skip
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SmokeTestError(f"{method} {url} -> HTTP {exc.code}") from exc


def wait_for_processed(
    count_fn: Callable[[], int],
    expected: int,
    timeout_s: float = POLL_TIMEOUT_S,
    interval_s: float = POLL_INTERVAL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Poll ``count_fn`` until it reaches ``expected`` or the timeout passes."""
    deadline = clock() + timeout_s
    while True:
        current = count_fn()
        if current >= expected:
            return current
        if clock() >= deadline:
            raise SmokeTestError(
                f"timeout: {current}/{expected} processed chunks after {timeout_s}s"
            )
        sleep(interval_s)


def check_api(base_url: str, fetch: Callable[[str], Any] = http_json) -> dict[str, Any]:
    """Call every route; each must return a non-empty JSON object. Returns the bodies."""
    results: dict[str, Any] = {}
    for route in API_ROUTES:
        body = fetch(f"{base_url.rstrip('/')}/{route}")
        if not isinstance(body, dict) or not body:
            raise SmokeTestError(f"/{route} returned empty or non-object JSON")
        results[route] = body
    if results["stats/accuracy"]["sample_size"] <= 0:
        raise SmokeTestError("accuracy route reports no reviews")
    if not any(d["total"] for d in results["stats/daily?days=14"]["series"]):
        raise SmokeTestError("daily series is all zeros")
    return results


def check_poison_queue(queue_client: Any) -> None:
    messages = list(queue_client.peek_messages(max_messages=5))
    if messages:
        raise SmokeTestError(f"poison queue is not empty ({len(messages)}+ message(s))")


def function_key(resource_group: str, app: str) -> str:
    az = shutil.which("az")
    if az is None:
        raise SmokeTestError("az not found on PATH")
    out = subprocess.run(
        [az, "functionapp", "keys", "list", "-g", resource_group, "-n", app,
         "--query", "functionKeys.default", "-o", "tsv"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return out.stdout.strip()


def terraform_outputs() -> dict[str, Any]:
    out = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=TF_ENV_DIR, capture_output=True, text=True, check=True,
    )  # fmt: skip
    return {k: v["value"] for k, v in json.loads(out.stdout).items()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--days", type=int, default=3, help="backfill_days to request (0 = skip backfill)"
    )
    p.add_argument("--backfill-only", action="store_true", help="call backfill and stop")
    p.add_argument("--dry-run", action="store_true", help="print what would run, call nothing")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        print(f"[dry-run] would POST backfill_days={args.days}, poll processed blobs, "
              f"call {len(API_ROUTES)} API routes and check the poison queue")  # fmt: skip
        return 0

    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient
    from azure.storage.queue import QueueClient

    out = terraform_outputs()
    credential = DefaultAzureCredential()
    blobs = BlobServiceClient(out["data_blob_url"], credential=credential)
    processed = blobs.get_container_client("processed")
    before = sum(1 for _ in processed.list_blobs())

    ingested = 0
    if args.days > 0:
        # Flex Consumption host names carry a generated suffix; take the real one from Terraform.
        backfill_url = f"https://{out['pipeline_hostname']}/api/ops/backfill"
        key = function_key(out["resource_group_name"], out["pipeline_app_name"])
        result = http_json(
            backfill_url, "POST", {"backfill_days": args.days}, {"x-functions-key": key}
        )
        ingested = len(result.get("ingested", []))
        print(f"backfill ingested {ingested} chunk(s); {result.get('remaining')} remaining")
    if args.backfill_only:
        return 0

    if ingested:
        wait_for_processed(lambda: sum(1 for _ in processed.list_blobs()), before + ingested)
        print(f"{ingested} new processed chunk(s) found")
    else:
        print("nothing new to wait for (no chunks ingested); checking the existing data")

    check_api(out["api_base_url"])
    print("API routes OK")

    poison = QueueClient(out["data_queue_url"], "enrich-poison", credential=credential)
    check_poison_queue(poison)
    print("poison queue empty")
    print(f"dashboard: {out['dashboard_url']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeTestError as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
