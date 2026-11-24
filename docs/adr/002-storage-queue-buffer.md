# ADR 002: Event Grid to a Storage Queue as the enrichment buffer

Status: Accepted

## Context
A new raw blob must trigger classification. Classifying 50 reviews takes minutes and calls an external AI service that can throttle (HTTP 429).

## Decision
Event Grid (system topic on the data account, `BlobCreated`, subject filter `/blobServices/default/containers/raw/` + `.jsonl`) delivers events into the **`enrich` Storage Queue** using the topic's managed identity. A queue-triggered function processes one message at a time (`batchSize 1`, `newBatchThreshold 0`) and failed messages move to `enrich-poison` after `maxDequeueCount 3`.

The brief's "subject prefix raw/" is corrected: blob event subjects include the container path, so a filter on `raw/` alone would never match.

## Consequences
- The queue absorbs bursts (a 10-day backfill) and survives function restarts; delivery is at-least-once, so enrichment is idempotent (existing processed blob = skip).
- Poison messages are visible and alertable instead of being retried forever.
- Event Grid writes plain JSON, so `host.json` sets `messageEncoding: none`.
- A direct Event Grid to Function endpoint would be simpler but gives no buffering, no poison queue and no concurrency control.
