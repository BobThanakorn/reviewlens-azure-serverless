# Cost

The subscription is **Azure for Students** (USD 100 credit, no payment method). This page lists what costs money, what this build actually used, and where to check. It contains **no prices**: prices change and differ by region, so read them from the official pages below.

## Design choices that keep cost low

- No always-on compute: both Function Apps run on **Flex Consumption** (scale to zero, `maximum_instance_count = 2`). No VM, AKS, fixed App Service plan or Front Door.
- Azure OpenAI is billed per token. `reasoning_effort = minimal` cut output from about 1,700 to about 50 tokens per review in Phase 0 (runbook incident 8).
- Data volume is capped: 500 reviews in 10 chunks; the timer stops ingesting when the chunks are used up.
- Storage is Standard LRS with soft delete (7-14 days), not geo-redundant.

## Cost drivers

| Resource | What is billed | Notes for this project |
|---|---|---|
| Azure OpenAI `gpt-5-nano` (GlobalStandard) | input and output tokens | Measured: 331,825 input and 25,272 output tokens for the full 500-review backfill (`docs/evaluation.md`). Capacity 50 is a rate limit, not a reservation. |
| Functions, Flex Consumption | executions, execution time x memory, always-ready instances (none configured) | Two apps, 2048 MB instances. One timer run a day, one queue message per chunk, HTTP API calls from the dashboard. |
| Storage accounts (5) | stored GB, transactions | Data lake about 1 MB of JSONL, two host accounts, web, Terraform state. Transactions dominate, still small. |
| Event Grid system topic | operations (events delivered) | One event per raw chunk: 10 in total. |
| Log Analytics / Application Insights | GB ingested, retention beyond the included period | The largest risk if logging is left verbose. Sampling is on; requests and exceptions are kept. |
| Scheduled query alerts (3) | per rule, by evaluation frequency | Check the frequency in `terraform/modules/monitoring` before adding more rules. |
| Budget (optional, off) | free | `enable_budget = false`; creating one has not been proven on this offer. |

**Placeholder:** monthly cost of this environment = _[fill in from Cost Management after a full month]_. Do not estimate it from memory.

## How to check spending and remaining credit

- Azure portal > **Cost Management** > Cost analysis, scoped to `rg-reviewlens-dev` (and `rg-reviewlens-tfstate`). Group by service to see the drivers above.
- Remaining student credit: Azure portal > **Subscriptions** > Azure for Students > Overview, or the sponsorship balance page at https://www.microsoftazuresponsorships.com/.
- Token usage per review is stored in every processed row (`input_tokens`, `output_tokens`), so `scripts/evaluate.py` reports the real total.

## Official pricing pages

- Azure OpenAI: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
- Azure Functions: https://azure.microsoft.com/pricing/details/functions/
- Blob storage: https://azure.microsoft.com/pricing/details/storage/blobs/
- Queue storage: https://azure.microsoft.com/pricing/details/storage/queues/
- Event Grid: https://azure.microsoft.com/pricing/details/event-grid/
- Azure Monitor (Log Analytics, alerts): https://azure.microsoft.com/pricing/details/monitor/
- Pricing calculator: https://azure.microsoft.com/pricing/calculator/

## Pause or tear down

- Pause ingestion only: see "Pause the daily timer" in `docs/runbook.md`.
- Remove everything that can cost money: `terraform -chdir=terraform/envs/dev destroy`, run by the owner (or the `destroy` workflow with `confirm=destroy`). The bootstrap stack (state account and CI identities) costs almost nothing; destroy it last, and only after the dev state is no longer needed.
