# Feasibility (Phase 0)

Status: **complete (2026-11-25).** Read-only checks plus one approved temporary Azure OpenAI test (all temporary resources deleted). Every value below was read from `az` output. Subscription id, tenant id, e-mail and the names of unrelated resources are deliberately left out because this file is committed.

## 0. Local tools

| Tool | Result |
|---|---|
| git | 2.54.0 |
| terraform | 1.17.2 (brief needs >= 1.10) |
| python | 3.12.10 |
| node | 24.19.0 (dashboard unit tests) |
| PowerShell | 7.7.0 |
| Azure CLI | 2.93.0 (installed by the owner on 2026-11-25) |
| tflint | 0.66.0, downloaded into the git-ignored `.tools/` after a SHA-256 check |

## 1. Subscription, regions, providers

- Offer: **Azure for Students**, `quotaId = AzureForStudents_2018-01-01`, state `Enabled`, `spendingLimit = On` (so no overage is possible).
- Signed-in user: **Owner** on the subscription. That is enough for the bootstrap stack (resource groups, role assignments, provider registration).
- Policy "Allowed resource deployment regions" (`sys.regionrestriction`) allows only: `japaneast`, `japanwest`, `indonesiacentral`, `southeastasia`, `eastasia`.
- **Chosen region: `southeastasia`** (allowed, closest to Thailand, supports everything below).
- The subscription already contains two resource groups from unrelated projects. This project never touches them, but their spend counts against the same USD 100 credit.

Resource providers (state before this project):

| Provider | State |
|---|---|
| Microsoft.Storage, CognitiveServices, ManagedIdentity, Consumption, Authorization, CostManagement | Registered |
| **Microsoft.Web, EventGrid, Insights, OperationalInsights, App, AlertsManagement** | **NotRegistered** |

The six unregistered providers must be registered once before the first apply (`az provider register --namespace <name>`). That is a change to the subscription, so it is listed in the Phase 7 checklist and not done now. Terraform is configured with `resource_provider_registrations = "none"` on purpose.

## 2. Functions hosting plans

- `az functionapp list-flexconsumption-locations`: Flex Consumption is available in all five allowed regions, including `southeastasia`.
- Flex Consumption Python runtimes in `southeastasia`: 3.10 (EOL 2026-10-31), 3.11, **3.12 (EOL 2028-10-31)**, 3.13, 3.14, 3.15.
- **Decision:** Flex Consumption (`FC1`), Python 3.12. It matches the interpreter used for tests (3.12.10).
- Not yet verified: whether the timer honours a time-zone setting on Flex Consumption (the design already avoids the question by using a UTC cron).

## 3. Azure OpenAI / Foundry

Read-only findings for `southeastasia`:

- Account quota `OpenAI.S0.AccountCount`: current 0, limit 1, so one OpenAI account can be created.
- Catalog and quota for small chat models (`GlobalStandard`, limits in thousands of tokens per minute):

| Model | Version | Lifecycle | Quota |
|---|---|---|---|
| gpt-5-nano | 2025-08-07 | GenerallyAvailable | 5000 |
| gpt-5.4-nano | 2026-03-17 | GenerallyAvailable | 5000 |
| gpt-4.1-nano | 2025-04-14 | Legacy | 5000 |
| gpt-4.1-mini | 2025-04-14 | Legacy | 5000 |
| gpt-4o-mini | 2024-07-18 | Deprecating | no quota entry |

- `japaneast` has `gpt-4o-mini` quota 2000 but it is a deprecating model, and `southeastasia` is closer.
- The `gpt-5` family is a reasoning family: it rejects `temperature=0` and `max_tokens` (it needs `max_completion_tokens`), and hidden reasoning tokens count toward the output limit. `OpenAIClassifier` currently sends the old parameters, so it must be adapted if a `gpt-5` model is chosen. `gpt-4.1-nano` accepts the current parameters but is marked Legacy.

### Deployment test (approved by the owner, 2026-11-25)

Temporary resources in `southeastasia`: a resource group, an OpenAI account (S0, custom sub-domain) and one `gpt-5-nano` deployment, called with Entra auth (`Cognitive Services OpenAI User` on that account). They were deleted afterwards and the soft-deleted account was purged; the OpenAI account quota is back to 0 of 1.

| Check | Result |
|---|---|
| Create account | Succeeded, no Azure Policy block |
| Create deployment `gpt-5-nano` (GlobalStandard) | Succeeded |
| Entra auth (no keys) | Works with the OpenAI User role |
| Project `OpenAIClassifier` on 3 Thai reviews | JSON valid, Thai summaries, all 3 returned `status=ok` (after the fixes below) |

What the test found (each one changed the code):

1. The first call failed with HTTP 400 `Unsupported parameter: 'max_tokens' ... Use 'max_completion_tokens'`. The gpt-5 family also rejects `temperature=0`. `OpenAIClassifier` now sends `max_completion_tokens` and no `temperature`.
2. Default reasoning is expensive for this task. Measured on the same 3 reviews:

| reasoning_effort | output tokens per review | latency |
|---|---|---|
| default (medium) | 947 to 1,725 | 5 to 10 s |
| **minimal** | **43 to 55** | **1.5 to 3.3 s** |

   Input was 606 to 914 tokens per review (few-shot prompt plus the review). `minimal` needs API version `2025-04-01-preview`; both are now defaults (`OPENAI_REASONING_EFFORT`, `OPENAI_API_VERSION`).
3. HTTP 429 handling was exercised for real. The 429 response carries `retry-after` and `x-ratelimit-*` headers. The first deployment had capacity 1 (1 request and 1,000 tokens per minute), which produced 429s and showed the backoff path working until it gave up after 5 attempts.
4. Raising the capacity of the existing deployment to 50 was stored correctly by Azure (50 RPM, 50K TPM) but the gateway kept enforcing the old limit for at least 5 minutes. **Deleting and recreating the deployment at capacity 50 fixed it immediately.** Terraform therefore sets capacity 50 at creation. Azure also reserves TPM quota from `max_completion_tokens`, so the default is 800 (minimal effort needs about 50).

The sample is tiny (3 reviews, all 3-star), so this proves feasibility and cost shape, not accuracy. Accuracy comes from `scripts/evaluate.py` after the real run.

## 4. Azure AI Language (fallback)

- Not needed (section 3 succeeded). If it is ever needed: a Language account (`TextAnalytics`, free tier F0) **already exists in `southeastasia`** in the subscription (unrelated project). Azure allows one F0 Language account per subscription and region, so the fallback in `southeastasia` would need the paid S tier or another region.
- Thai support for sentiment analysis: **not yet verified against current docs.** Only needed if section 3 fails.

## 5. Budgets

- `az consumption budget list` works and returns an empty list, so the Budgets API is reachable on this offer type.
- Whether a budget can be **created** is not proven (it needs a write). `enable_budget` stays `false` in Terraform; the first deploy can try it as a single reversible resource.

## Decision

**Provider `openai`**, region `southeastasia`, model `gpt-5-nano` (2025-08-07, GlobalStandard, capacity 50, `reasoning_effort=minimal`, API version `2025-04-01-preview`). The `language` provider stays implemented and tested as the fallback. Recorded in `docs/adr/000-ai-provider.md`.

Open items for the deploy phase: register the six providers (section 1), verify role-definition GUIDs, try the budget (section 5).
