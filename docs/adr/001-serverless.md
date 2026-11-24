# ADR 001: Serverless compute on Azure Functions (Flex Consumption)

Status: Accepted (hosting plan availability in the chosen region is verified in Phase 0)

## Context
The workload is bursty: one small chunk per day plus occasional demo backfills. The subscription has a fixed USD 100 credit, and the brief forbids any always-on cost (VMs, AKS, fixed-SKU App Service plans).

## Decision
Run both Function Apps (Python v2 model) on **Flex Consumption** (`FC1`), max 2 instances each. If the region lacks Flex Consumption, fall back to the current recommended serverless plan and amend this ADR.

The daily timer is written in **UTC** (`0 0 1 * * *` = 08:00 Asia/Bangkok) because Flex Consumption does not support the `WEBSITE_TIME_ZONE` setting (verify against current docs before deploy).

## Consequences
- Scales to zero, so an idle project costs close to nothing; cold starts of a few seconds are acceptable for batch work.
- `maximum_instance_count = 2` bounds both concurrency and spend.
- Code is not deployed by Terraform; `scripts/deploy_functions.py` publishes the package.
- Bangkok has no daylight saving, so a fixed UTC cron stays correct all year.
