"""func-pipeline: daily ingest (timer), admin backfill (HTTP) and enrich (queue trigger).

Kept thin on purpose: all logic lives in ``pipeline.ingest`` and ``pipeline.enrich`` so it can
be tested without the Functions host. Connections use managed identity (no keys):
  * AzureWebJobsStorage__accountName            host storage (timer leases, etc.)
  * DataStorage__queueServiceUri                queue trigger connection
  * DATA_BLOB_URL                               blob endpoint used through BlobStore
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import azure.functions as func

from common.classifier import get_classifier
from common.config import Settings
from common.storage import BlobStore
from pipeline.enrich.handler import handle_message
from pipeline.ingest.handler import BadRequestError, run_backfill, run_daily

app = func.FunctionApp()


@lru_cache(maxsize=1)
def get_store() -> BlobStore:
    return BlobStore.from_account_url(Settings.from_env().data_blob_url)


@lru_cache(maxsize=1)
def get_cached_classifier() -> Any:
    return get_classifier(Settings.from_env())


def json_response(status: int, body: dict[str, Any]) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body, ensure_ascii=False), status_code=status, mimetype="application/json"
    )


def backfill_request(raw_body: bytes) -> tuple[int, dict[str, Any]]:
    try:
        body = json.loads(raw_body or b"null")
        return 200, run_backfill(get_store(), body).as_dict()
    except (json.JSONDecodeError, BadRequestError) as exc:
        return 400, {"error": str(exc)}


# 08:00 Asia/Bangkok = 01:00 UTC. Flex Consumption has no time-zone setting, so the cron is UTC.
# To pause: set app setting AzureWebJobs.daily_ingest.Disabled=true (see docs/runbook.md).
@app.timer_trigger(schedule="0 0 1 * * *", arg_name="timer", run_on_startup=False)
def daily_ingest(timer: func.TimerRequest) -> None:
    result = run_daily(get_store())
    logging.info("daily_ingest finished: %s", result.as_dict())


@app.route(route="ops/backfill", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def backfill(req: func.HttpRequest) -> func.HttpResponse:
    status, body = backfill_request(req.get_body())
    return json_response(status, body)


@app.queue_trigger(arg_name="msg", queue_name="enrich", connection="DataStorage")
def enrich(msg: func.QueueMessage) -> None:
    # Exceptions propagate on purpose: the runtime retries and finally moves the message to
    # the poison queue after maxDequeueCount (3).
    handle_message(get_store(), get_cached_classifier(), msg.get_body().decode("utf-8"))
