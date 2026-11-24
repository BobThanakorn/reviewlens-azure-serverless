# Requirements

Status: DRAFT, awaiting approval. Source: `docs/PROJECT_BRIEF.md`.
Notation: EARS (Easy Approach to Requirements Syntax).
Personas: **Analyst** (reads the dashboard), **Operator** (the engineer running the pipeline), **Reviewer** (a hiring manager reading the repo).

## R1. Daily ingestion
*As an Operator, I want new reviews to arrive automatically every day, so the pipeline behaves like a real feed.*

1. WHEN the daily timer fires (08:00 Asia/Bangkok), THE ingest function SHALL read `state/next_chunk.json`, copy `source/chunks/NNNNNN.jsonl` to `raw/dt=YYYY-MM-DD/chunk-NNNNNN.jsonl` adding `ingested_at` to every line, and advance the state.
2. THE ingest function SHALL update the state with an ETag `If-Match` condition.
3. IF the ETag condition fails (HTTP 412), THEN THE ingest function SHALL log a warning and stop without ingesting a second chunk.
4. IF no chunk remains in `source`, THEN THE ingest function SHALL log "no more chunks" and finish successfully.
5. WHERE the plan does not support a time-zone setting, THE timer schedule SHALL be expressed in UTC (`0 0 1 * * *`).

## R2. Admin backfill
*As an Operator, I want to ingest several days at once for demos.*

1. WHEN an authorised caller POSTs `{"backfill_days": N}` with a valid function key, THE backfill function SHALL ingest up to N chunks dated `today-N+1 ... today`.
2. IF `N` is missing, not an integer, or outside 1..10, THEN THE function SHALL return HTTP 400 and ingest nothing.
3. IF the function key is missing or wrong, THEN THE platform SHALL return HTTP 401.
4. IF fewer than N chunks remain, THEN THE function SHALL ingest what remains and report the count.

## R3. Enrichment
*As an Analyst, I want every review labelled with sentiment, topic and a short summary.*

1. WHEN a blob matching `raw/**/*.jsonl` is created, THE Event Grid subscription SHALL deliver the event to the `enrich` storage queue.
2. WHEN a queue message arrives, THE enrich function SHALL classify each review and write `processed/dt=YYYY-MM-DD/chunk-NNNNNN.jsonl` with the same chunk name as the input.
3. THE enrich function SHALL process one message at a time (batch size 1, newBatchThreshold 0).
4. WHEN the processed blob already exists for the input, THE enrich function SHALL skip classification (idempotent, saves cost) unless the message sets `force=true`.
5. IF the classifier returns invalid output, THEN THE enrich function SHALL re-ask once; IF it is still invalid, THEN it SHALL set `sentiment="unknown"`, `topic="unknown"`, `status="invalid_output"`.
6. IF the classifier returns HTTP 429, THEN THE enrich function SHALL retry with exponential backoff and jitter, at most 5 attempts.
7. IF processing fails with an unhandled error 3 times (`maxDequeueCount=3`), THEN THE platform SHALL move the message to the poison queue.
8. THE enrich function SHALL emit structured JSON logs with reviews processed, failures, latency and token usage.

## R4. Classifier provider
*As an Operator, I want to switch AI providers without code changes, because Azure OpenAI may be blocked.*

1. THE system SHALL expose one `Classifier` interface in `src/common/classifier.py` with a `openai` and a `language` implementation.
2. WHEN the app setting `CLASSIFIER_PROVIDER` is `openai` or `language`, THE factory SHALL return the matching implementation; any other value SHALL raise a configuration error at start-up.
3. WHERE provider is `language`, THE classifier SHALL take sentiment from Azure AI Language, topic from a Thai keyword rule table, and summary as the first 120 characters.
4. THE classifier output SHALL satisfy: sentiment in {positive, neutral, negative}, topic in {food, service, price, atmosphere, cleanliness, other}, Thai summary <= 120 characters.
5. WHILE developing, THE system SHALL NOT send more than 20 reviews to a real classifier without the user's confirmation.

## R5. Read-only API
*As an Analyst, I want the dashboard to get aggregated data over HTTP.*

1. THE API SHALL expose `GET /api/stats/daily?days=14`, `/api/stats/topics`, `/api/stats/accuracy`, `/api/reviews?sentiment=negative&limit=20`.
2. WHEN a parameter is outside its whitelist/range (`days` 1..30, `limit` 1..100, `sentiment` in the allowed set), THE API SHALL return HTTP 400 with a JSON error and no stack trace.
3. THE API SHALL accept only GET (and OPTIONS for CORS) and SHALL NOT write to storage.
4. THE API SHALL allow cross-origin requests only from the static website origin.
5. THE accuracy route SHALL use ground truth stars 1-2 = negative, 3 = neutral, 4-5 = positive, and SHALL return accuracy, sample size and a confusion matrix; reviews labelled `unknown` count as wrong.
6. THE API SHALL de-duplicate by `review_id` before aggregating.
7. IF there is no processed data in the range, THEN THE API SHALL return HTTP 200 with zero counts, not an error.

## R6. Dashboard
*As an Analyst, I want a single page that shows trends and accuracy.*

1. THE dashboard SHALL show KPI tiles (total reviews, % negative, accuracy), a daily sentiment line chart, a topic bar chart, and a table of the latest negative reviews.
2. THE dashboard SHALL read the API URL from `config.js` generated by Terraform; no URL SHALL be hard-coded.
3. IF an API call fails, THEN THE dashboard SHALL show an error message in that panel and keep the others working.
4. THE dashboard SHALL render review text as text (no `innerHTML`) to prevent XSS.

## R7. Evaluation
*As a Reviewer, I want measured accuracy, not claims.*

1. WHEN `scripts/evaluate.py` runs, IT SHALL read processed blobs and write `docs/evaluation.md` with sample size, accuracy, confusion matrix, and 5 misclassified examples (text truncated to 200 characters) with a short analysis.
2. THE numbers in `docs/evaluation.md` SHALL come from a real run, never hand-written.

## R8. Security
1. THE function apps SHALL use managed identities with RBAC; app settings SHALL contain no keys or connection strings (exceptions need an ADR).
2. THE `api` identity SHALL hold only `Storage Blob Data Reader` scoped to the `processed` container; no write and no AI roles.
3. THE `pipeline` identity SHALL hold `Storage Blob Data Contributor`, `Storage Queue Data Contributor` on the data account, plus the AI user role when `openai` is used.
4. THE data storage account SHALL enforce HTTPS, TLS 1.2, no public blob access, soft delete, and shared-key access disabled where the platform allows.
5. THE repository SHALL NOT contain secrets, subscription/tenant IDs, e-mail addresses, tfvars, or state files.
6. THE CI pipeline SHALL run Checkov; every skip SHALL carry an inline justification.
7. THE CI plan identity SHALL be read-only on the app resource group.

## R9. Observability
1. THE system SHALL have a Log Analytics workspace (30-day retention, daily cap) and workspace-based Application Insights.
2. WHEN the poison queue holds a message, THE system SHALL fire an alert to the action group e-mail.
3. WHEN there is any function failure in a 5-minute window, THE system SHALL fire an alert.
4. WHEN enrich duration approaches its timeout, THE system SHALL fire an alert.
5. THE dashboard/workbook SHALL show reviews ingested per day, enrich failures, classifier latency, and queue length.
6. WHERE consumption budgets are supported (see feasibility), THE system SHALL create a resource-group budget with 50% and 100% alerts; otherwise the limitation SHALL be documented.

## R10. Infrastructure as code and CI/CD
1. THE infrastructure SHALL be provisioned only by Terraform (>= 1.10), with remote state in Azure Storage using Entra auth and blob lease locking.
2. THE `terraform/bootstrap` stack SHALL create the state storage, resource groups, and two user-assigned managed identities with GitHub OIDC federated credentials (plan: `pull_request`; apply: `refs/heads/main`).
3. WHEN a pull request is opened, `ci.yml` SHALL run ruff, pytest, terraform fmt/validate, tflint, checkov and `terraform plan`, then post the plan summary as a PR comment.
4. WHEN code is pushed to `main`, `deploy.yml` SHALL run the same checks, `terraform apply`, deploy function code, upload web assets, and run the smoke test.
5. WHEN `destroy.yml` is started with `confirm != "destroy"`, THE workflow SHALL refuse to run.
6. THE system SHALL be re-creatable with one command (`scripts/tasks.py deploy`) and every step SHALL be idempotent.
7. EVERY resource SHALL carry tags `Project=reviewlens`, `Environment=dev`, `ManagedBy=terraform`.

## R11. Cost control
1. THE system SHALL NOT use always-on-cost resources (VMs, AKS, fixed-SKU App Service Plans, Front Door, Application Gateway, provisioned Cosmos DB, Synapse/Fabric/Databricks).
2. THE dataset SHALL be limited to 500 reviews (10 chunks of 50) and the backfill to 10 days.
3. BEFORE the first `terraform apply`, THE assistant SHALL show the plan summary, flag recurring cost, and wait for confirmation.
4. THE assistant SHALL NOT upgrade the subscription or add a payment method.
5. THE docs SHALL explain how to check remaining credit and how to pause or destroy; prices SHALL NOT be invented.

## R12. Data bootstrap
1. WHEN `scripts/bootstrap_data.py` runs, IT SHALL download Wongnai `train`, drop empty reviews, sample 500 rows (seed 42), assign `review_id`, split into 50-row chunks, and upload `source/chunks/000001.jsonl ...` with Entra auth.
2. THE script SHALL be idempotent (re-run gives identical blobs).
3. THE script SHALL write `sample-data/sample.jsonl` (20 rows), the only dataset content committed to git.
4. THE README SHALL credit the dataset and its LGPL-3.0 license.

## R13. Quality and documentation
1. `ruff check` SHALL pass; `pytest` SHALL pass with coverage >= 80% for `src/`; tests SHALL need no Azure.
2. THE repo SHALL contain README, ADR 000-006 (+ any changed decision), runbook with real incidents, cost, github-setup, evaluation, feasibility, and a README per Terraform module.
3. WHEN the brief conflicts with current Azure/Terraform docs, THE assistant SHALL follow the docs and record an ADR.

## R14. Feasibility (Phase 0)
1. BEFORE any build, THE assistant SHALL record real results in `docs/feasibility.md`: subscription type, allowed regions, resource providers, Functions hosting plans in the chosen region, Azure OpenAI feasibility (and quota), Azure AI Language Thai support, and budget support.
2. THE assistant SHALL use read-only `az` commands first and ask before creating any temporary resource, deleting it right after.
3. THE AI provider decision SHALL be recorded in ADR 000.

## Out of scope
Multi-environment, Key Vault/CMK, PII masking, Durable Functions, Entra auth in front of the API, SQL/Fabric analytics (listed as "Production next steps"). Azure SQL serverless is a stretch goal after the Definition of Done.
