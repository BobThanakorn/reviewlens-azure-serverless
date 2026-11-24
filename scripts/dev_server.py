"""Run the dashboard locally against MOCK data. No Azure, no AI calls, nothing is uploaded.

Serves web/ plus /api/* using the real API code (src/api) on an in-memory store filled with
synthetic labels, so the whole read path can be viewed before anything is deployed:

    python scripts/dev_server.py            # then open http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import UTC, datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from api.handler import handle  # noqa: E402
from common.models import TOPICS, dated_blob_name, today_bangkok  # noqa: E402

WEB_DIR = ROOT / "web"
SAMPLE = ROOT / "sample-data" / "sample.jsonl"
DAYS = 10
PER_DAY = 50


class MemoryStore:
    """The few BlobStore methods the API uses, backed by a dict."""

    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], str] = {}

    def write_text(self, container: str, name: str, text: str) -> None:
        self.blobs[(container, name)] = text

    def read_text(self, container: str, name: str) -> str:
        return self.blobs[(container, name)]

    def list_names(self, container: str, prefix: str = "") -> list[str]:
        return sorted(n for (c, n) in self.blobs if c == container and n.startswith(prefix))


def synthetic_label(stars: int, rng: random.Random) -> str:
    """Mostly agrees with the stars, sometimes not, so the confusion matrix has content."""
    truth = "negative" if stars <= 2 else "neutral" if stars == 3 else "positive"
    if rng.random() < 0.7:
        return truth
    return rng.choice([s for s in ("positive", "neutral", "negative") if s != truth])


def build_store(days: int = DAYS, per_day: int = PER_DAY, seed: int = 7) -> MemoryStore:
    rng = random.Random(seed)  # noqa: S311 - mock data only
    texts = [json.loads(line) for line in SAMPLE.read_text(encoding="utf-8").splitlines()]
    today = today_bangkok()
    store = MemoryStore()
    review_id = 0
    for chunk in range(1, days + 1):
        dt = today - timedelta(days=days - chunk)
        lines = []
        for _ in range(per_day):
            review_id += 1
            base = texts[review_id % len(texts)]
            stars = rng.choices([1, 2, 3, 4, 5], weights=[2, 5, 30, 45, 18])[0]
            sentiment = synthetic_label(stars, rng)
            lines.append(
                json.dumps(
                    {
                        "review_id": review_id,
                        "review_text": base["review_text"],
                        "stars": stars,
                        "sentiment": sentiment,
                        "topic": rng.choice(TOPICS),
                        "summary": base["review_text"][:60],
                        "status": "ok",
                        "provider": "mock",
                        "model": "mock",
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "processed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                    ensure_ascii=False,
                )
            )
        store.write_text("processed", dated_blob_name(dt, chunk), "\n".join(lines) + "\n")
    return store


class Handler(SimpleHTTPRequestHandler):
    store: MemoryStore

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parts = urlsplit(self.path)
        if parts.path == "/config.js":
            self._send(
                200, 'window.REVIEWLENS_CONFIG = { apiBaseUrl: "/api" };\n', "text/javascript"
            )
        elif parts.path.startswith("/api/"):
            status, body = handle(
                self.store, parts.path[len("/api/") :], dict(parse_qsl(parts.query))
            )
            self._send(status, json.dumps(body, ensure_ascii=False), "application/json")
        else:
            super().do_GET()

    def _send(self, status: int, text: str, content_type: str) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[mock] {fmt % args}\n")


def make_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = type("MockHandler", (Handler,), {"store": build_store()})
    return ThreadingHTTPServer((host, port), partial(handler, directory=str(WEB_DIR)))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv)
    server = make_server(port=args.port)
    print(f"MOCK DATA ONLY. Dashboard: http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
