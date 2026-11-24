"""func-api: read-only HTTP routes under /api. Anonymous by design (public, read-only data);
see docs/adr/005-anonymous-read-api.md. The identity behind it can only read ``processed``."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import azure.functions as func

from api.handler import cors_headers, handle
from common.config import Settings
from common.storage import BlobStore

app = func.FunctionApp()


@lru_cache(maxsize=1)
def get_store() -> BlobStore:
    return BlobStore.from_account_url(Settings.from_env().data_blob_url)


def respond(route: str, params: dict[str, str], origin: str | None) -> tuple[int, dict, dict]:
    status, body = handle(get_store(), route, params)
    return status, body, cors_headers(origin, Settings.from_env().web_origin)


def to_http(status: int, body: dict[str, Any], headers: dict[str, str]) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body, ensure_ascii=False),
        status_code=status,
        mimetype="application/json",
        headers=headers,
    )


@app.route(route="{*route}", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.ANONYMOUS)
def api(req: func.HttpRequest) -> func.HttpResponse:
    origin = req.headers.get("Origin")
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=204, headers=cors_headers(origin, Settings.from_env().web_origin)
        )
    status, body, headers = respond(req.route_params.get("route", ""), dict(req.params), origin)
    return to_http(status, body, headers)
