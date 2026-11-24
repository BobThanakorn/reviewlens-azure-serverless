# ADR 003: Blob storage with JSONL files as the data lake

Status: Accepted

## Context
500 reviews, read by a small API and a dashboard. The brief rules out provisioned databases and analytics workspaces (always-on cost).

## Decision
Keep every stage as JSONL blobs in one storage account: `source/chunks/NNNNNN.jsonl` to `raw/dt=YYYY-MM-DD/chunk-NNNNNN.jsonl` to `processed/dt=YYYY-MM-DD/chunk-NNNNNN.jsonl`. The processed blob has the **same name** as its input and is written in one upload. State lives in `state/next_chunk.json`, updated with an ETag condition.

## Consequences
- Idempotent by construction: reprocessing overwrites the same blob; a half-written chunk cannot exist.
- `dt=` prefixes make date-range reads cheap (list by prefix) with no index.
- Aggregation happens in Python at request time; fine for hundreds of rows, not for millions. Azure SQL serverless or Fabric are listed under production next steps.
- The API de-duplicates by `review_id` to tolerate a re-ingested chunk after a crash.
