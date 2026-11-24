# ReviewLens: Serverless Data & AI Pipeline on Azure - Project Brief

Instructions for Claude Code. Source of truth for the whole project. Persistent rules also live in CLAUDE.md.

## 0. Working agreement

- Talk to me in Thai. Write all code, comments, commit messages and documentation in English.
- Start in plan mode. Read this brief, then write docs/spec/requirements.md (user stories with EARS acceptance criteria), docs/spec/design.md (architecture, data flow, schemas, RBAC, error handling) and docs/spec/tasks.md (checkbox list ordered by the PHASES below; every task ends with a verification step). Show me the plan and wait for approval before editing anything else.
- Then execute tasks in order. After each task: run the relevant checks (ruff, pytest, terraform fmt/validate), fix failures before moving on, tick the task in docs/spec/tasks.md, commit with a Conventional Commits message.
- Make reasonable decisions yourself and record significant ones as ADRs in docs/adr/. Stop only for the HUMAN-ONLY STEPS and the DEPLOY PAUSE.
- If anything in this brief is technically wrong or outdated (a service limit, a provider argument, a deprecated resource), follow current Azure and Terraform documentation, fix it, and record the change in an ADR. Do not silently skip requirements.
- If the session is long, re-read the relevant section of this brief and docs/spec/tasks.md before starting each phase.

## 1. Project

Name: ReviewLens: Serverless Data & AI Pipeline on Azure
Repo: reviewlens-azure-serverless
Tagline: A serverless data and AI pipeline on Azure that ingests Thai restaurant reviews daily, classifies them with an LLM, and serves analytics through a dashboard. Fully provisioned with Terraform and deployed through GitHub Actions.
Story: a restaurant chain receives reviews daily and nobody has time to read them. ReviewLens ingests new reviews every day, classifies sentiment and topic, shows trends on a dashboard, and measures the classifier's accuracy against customers' star ratings.
Audience: hiring managers for a junior Cloud Engineer role (AWS, Azure or GCP experience is welcome). The repo must demonstrate cloud infrastructure, data & AI, infrastructure as code, automation, security, observability, troubleshooting and documentation skills.

## 2. Environment

- Windows 11, PowerShell 7 (pwsh). Local helper scripts must be cross-platform Python (scripts/*.py) or PowerShell; do not rely on bash or make locally. GitHub Actions runs on ubuntu-latest and calls the same Python scripts.
- Python: always use a virtual environment at .venv; never pip install globally. Keep requirements.txt (runtime deps of the Function Apps, pinned) separate from requirements-dev.txt (pytest, ruff, checkov, etc.). Add .venv/ to .gitignore.
- Verify git, az, terraform, python are available before starting; if something is missing, tell me in Thai exactly how to install it.

## 3. Account constraints (Azure for Students) - read first

- The subscription is Azure for Students: USD 100 credit, spending protection, no pay-as-you-go. NEVER upgrade the subscription, add a payment method, or create resources whose cost could exceed the remaining credit. Credit expires around early February 2027. If it runs out the subscription is cancelled and resources disappear, so everything must be re-creatable with one command.
- Allowed regions are restricted by Azure Policy ("Allowed resource deployment regions") and differ per person. Read the allowed list first, prefer the allowed region closest to Thailand (Southeast Asia if allowed), and expose it as variable location. Deploy only inside allowed regions.
- Azure OpenAI / Microsoft Foundry may be blocked (RequestDisallowedByAzure) or have zero quota on this subscription. See PHASE 0.
- I may not be able to create Entra app registrations. Use user-assigned managed identities with federated credentials for GitHub OIDC.
- Register any resource providers needed (Microsoft.Web, Storage, EventGrid, Insights, OperationalInsights, CognitiveServices, ManagedIdentity, Consumption, Authorization).

## 4. Fixed tech decisions

- Terraform >= 1.10, azurerm provider pinned to the latest stable (add azapi only if azurerm lacks a needed feature). Remote state in an Azure Storage container with Entra auth (use_azuread_auth) and the backend's native blob lease locking.
- Two Azure Function Apps (Python v2 programming model, latest GA runtime supported, the current recommended serverless hosting plan available in my region, prefer Flex Consumption, max 2 instances each):
  - func-pipeline: ingest (timer + admin backfill HTTP) and enrich (queue trigger)
  - func-api: read-only HTTP routes
  Each app has its own managed identity.
- Identity-based connections (managed identity + RBAC) everywhere possible. No connection strings or keys in app settings unless the platform makes it impossible (then document in an ADR).
- Tests: pytest with mocks (no Azure needed). Lint: ruff. Coverage >= 80% for src/.
- CI/CD: GitHub Actions with azure/login OIDC. No client secrets anywhere.
- Nothing with always-on cost: no VMs, AKS, fixed-SKU App Service Plans, Front Door, Application Gateway, provisioned-throughput Cosmos DB, or Synapse/Fabric/Databricks workspaces.

## 5. Data

Source: Hugging Face dataset Wongnai/wongnai_reviews (LGPL-3.0; fields review_body, star_rating; train split).
scripts/bootstrap_data.py (runs locally):
- Download the train split, drop empty reviews, take a random sample of 500 rows (seed 42), assign review_id.
- Split into chunks of 50 rows and upload as JSONL to container source, blobs chunks/000001.jsonl, 000002.jsonl, ... with Entra auth (DefaultAzureCredential).
- Each line: {"review_id": int, "review_text": str, "stars": int}
- Write sample-data/sample.jsonl (20 rows) for tests. This is the only dataset content committed to git.
- Credit the dataset and its license in the README.

## 6. PHASE 0 feasibility (before building anything)

Write docs/feasibility.md with the real results of these checks (az CLI; create temporary resources only when needed and delete them immediately):
1. Subscription type and ID (confirm Azure for Students), allowed regions, registered resource providers.
2. Hosting plan availability for Functions in my region.
3. Azure OpenAI / Foundry: can I create a resource, list models, deploy a small low-cost chat model, and what is the quota? Test a Thai review if possible.
4. If (3) fails, test Azure AI Language sentiment analysis with Thai text (verify Thai support in current docs).
5. Whether consumption budgets are supported on this subscription type.
Decide the AI provider: "openai" if feasible, otherwise "language". Implement the classifier behind one interface in src/common/classifier.py with both providers and tests, selected by app setting CLASSIFIER_PROVIDER. Fallback "language" behaviour: sentiment from Azure AI Language, topic from a Thai keyword rule table, summary = first 120 characters. Record the decision in ADR 000. Tell me in Thai what you found and which path you took, then continue.

## 7. Architecture (implement all of it)

1. storage module
   - Data storage account: HTTPS only, TLS 1.2, no public blob access, shared key disabled if feasible, soft delete. Containers: source, raw, processed, state. Storage queue enrich (+ poison queue).
   - Separate storage account for the static website dashboard (public read of static files only).
   - Globally unique names get a random suffix.

2. ingest (simulates daily arrival of new reviews), in func-pipeline
   - Timer trigger daily 08:00 Asia/Bangkok (write the cron in UTC if the plan requires). Reads state/next_chunk.json (use ETag conditions for safe updates), copies that chunk to raw/dt=YYYY-MM-DD/chunk-NNNNNN.jsonl adding "ingested_at", increments the state. When chunks run out, log and exit successfully.
   - HTTP-triggered admin function (function-key auth) {"backfill_days": N} ingests N chunks dated today-N+1 ... today, for demos.

3. enrich, in func-pipeline
   - Event Grid system topic on the data account: BlobCreated, subject prefix raw/, suffix .jsonl -> Storage Queue. Queue-triggered function with batch size 1, newBatchThreshold 0 and maxDequeueCount 3 so repeated failures land in the poison queue.
   - For each review call the classifier. Prompt in src/pipeline/enrich/prompt.py: system prompt with rules plus 3 few-shot examples you write yourself (not from the dataset). Strict JSON output:
     sentiment: positive | neutral | negative
     topic: food | service | price | atmosphere | cleanliness | other
     summary: Thai, max 120 characters
   - Validate output; re-ask once; if still invalid set sentiment/topic "unknown" and status "invalid_output". Retry throttling (HTTP 429) with exponential backoff and jitter, max 5 attempts.
   - Write processed/dt=YYYY-MM-DD/chunk-NNNNNN.jsonl (same name as the input, so reprocessing is idempotent). Fields: review_id, review_text, stars, sentiment, topic, summary, status, provider, model, input_tokens, output_tokens, processed_at.
   - Structured JSON logs: reviews processed, failures, latency, token usage.

4. api (func-api, HTTP, read-only)
   GET /api/stats/daily?days=14, /api/stats/topics, /api/stats/accuracy, /api/reviews?sentiment=negative&limit=20
   - Read processed blobs for the requested date range and aggregate in Python (data is small). Strict input validation and whitelists. CORS limited to the static website origin.
   - Anonymous auth is acceptable because the data is public and the API is read-only; document this trade-off in an ADR and list "Entra ID auth + Front Door/WAF" under production next steps.
   - Ground truth for accuracy: stars 1-2 negative, 3 neutral, 4-5 positive. Also return the confusion matrix.

5. web
   - web/index.html + web/app.js with Chart.js from a CDN: KPI tiles (total reviews, % negative, accuracy), daily sentiment line chart, topic bar chart, table of latest negative reviews. web/config.js generated by Terraform with the API URL. Uploaded to the static website container during deploy.

6. monitoring
   - Log Analytics workspace (30-day retention, daily cap set) and workspace-based Application Insights.
   - Action group with email (variable alert_email). Alerts: poison queue has messages; function failures > 0 in 5 minutes; enrich duration approaching its timeout.
   - Dashboard or workbook: reviews ingested per day, enrich failures, classifier latency, queue length.
   - Resource-group budget (variable monthly_budget_usd) with 50% and 100% alerts if supported (see feasibility); otherwise document and skip.

7. bootstrap stack (terraform/bootstrap/, local state, applied once by me)
   - Resource groups: rg-reviewlens-tfstate and rg-reviewlens-dev. State storage account + container (versioned, TLS-only, Entra auth).
   - Two user-assigned managed identities with federated credentials for GitHub (variable github_repo):
     plan identity: Reader on the app RG + read on state; subject repo:<owner/repo>:pull_request
     apply identity: Contributor + User Access Administrator scoped to the app RG only + Storage Blob Data Contributor on state; subject repo:<owner/repo>:ref:refs/heads/main
   - Output the client IDs, tenant ID and subscription ID (not secrets) for GitHub repository variables.

8. Security everywhere (RBAC split)
   - pipeline identity: Storage Blob Data Contributor on the data account, Storage Queue Data Contributor, and the AI user role when applicable.
   - api identity: Storage Blob Data Reader scoped to the processed container only. It must have no write or AI permissions.
   - Roles are scoped to exact resources. Checkov runs in CI; every skip needs an inline justification.

## 8. CI/CD (.github/workflows/)

- ci.yml (pull_request): ruff, pytest, terraform fmt -check, validate, tflint (azurerm ruleset), checkov, terraform plan with the plan identity, post the plan summary as a PR comment.
- deploy.yml (push to main): same checks, terraform apply with the apply identity, deploy function code (scripts/deploy_functions.py), upload web assets, run scripts/smoke_test.py.
- destroy.yml (workflow_dispatch): requires input confirm = "destroy".
- Repository variables: AZURE_CLIENT_ID_PLAN, AZURE_CLIENT_ID_APPLY, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, AZURE_LOCATION.

## 9. Repo structure

reviewlens-azure-serverless/
  CLAUDE.md, README.md, LICENSE (MIT for code), .gitignore, pyproject.toml, requirements.txt, requirements-dev.txt
  .claude/settings.json
  docs/ PROJECT_BRIEF.md, spec/ (requirements.md, design.md, tasks.md), feasibility.md, architecture.md, adr/, runbook.md, evaluation.md, cost.md, github-setup.md
  terraform/bootstrap/, terraform/envs/dev/ (main.tf, backend.tf, variables.tf, outputs.tf, terraform.tfvars.example), terraform/modules/ storage, functions, eventing, monitoring, web
  src/ pipeline/ (function_app.py, ingest/, enrich/), api/ (function_app.py), common/
  web/, tests/
  scripts/ tasks.py, bootstrap_data.py, deploy_functions.py, smoke_test.py, evaluate.py
  sample-data/sample.jsonl
  .github/workflows/

scripts/tasks.py is a small cross-platform task runner with subcommands: init, fmt, lint, test, plan, deploy, deploy-functions, bootstrap-data, backfill (--days N), smoke-test, evaluate, destroy. A Makefile that forwards to it is optional and only for convenience.

## 10. Scripts

- smoke_test.py: invoke backfill 3, poll until processed blobs exist (max 10 minutes), call every API route and assert valid non-empty JSON, assert the poison queue is empty, print the dashboard URL.
- evaluate.py: read processed blobs, compute accuracy and the confusion matrix, write docs/evaluation.md with sample size, accuracy, matrix table, and 5 misclassified examples (text truncated to 200 characters) with a short analysis of why the model was wrong.

## 11. Documentation

- README.md top section in this order: title, tagline, CI badge, architecture diagram as Mermaid, "Skills demonstrated" table linking to the files that prove each skill, key results (accuracy, reviews processed). Then prerequisites, quickstart, how it works, cost and teardown, dataset credit and license, "Production next steps" (multi-environment, Key Vault + CMK, PII masking before the LLM, Durable Functions for large files, Entra auth + Front Door/WAF, SQL/Fabric analytics).
- docs/adr/: 000-ai-provider, 001-serverless, 002-storage-queue-buffer, 003-blob-jsonl-datalake, 004-github-oidc-managed-identity, 005-anonymous-read-api, 006-split-function-apps-by-privilege, plus any decision you change from this brief.
- docs/runbook.md: every real error hit during this build (symptom, root cause, fix, prevention) plus procedures: reprocess a day, drain the poison queue, change model, pause the timer.
- docs/cost.md: cost drivers, how to check remaining credit, links to official pricing pages and the Azure pricing calculator. Never invent prices; mark placeholders clearly.
- docs/github-setup.md: repo description, topics (azure, terraform, serverless, infrastructure-as-code, data-pipeline, azure-functions, github-actions), repository variables.
- Every Terraform module has a README listing inputs and outputs.
- Optional stretch (only after the Definition of Done): an Azure SQL serverless layer for SQL analytics, if provisioning is allowed on this subscription.

## 12. Rules

- Never commit secrets, subscription or tenant IDs, email addresses or tfvars. Provide *.example files. .gitignore covers .terraform/, *.tfstate*, *.tfvars, .env, .venv/, local.settings.json.
- Tags on everything: Project=reviewlens, Environment=dev, ManagedBy=terraform. Resource names are prefixed rl-dev or similar.
- Do all local work first (code, tests, terraform validate, docs). Before any Azure action run az account show and show me the subscription name and location.
- COST CONTROL: use 500 reviews and a 10-day backfill. During development call the classifier on at most 20 reviews (sample-data/sample.jsonl). Run larger sets only after I confirm. Before the first terraform apply show the plan summary and flag anything with recurring cost; wait for my confirmation.
- Create .claude/settings.json with deny rules for destructive commands (at least terraform destroy, az group delete, az role assignment delete, git push --force) using the current permission rule syntax from the Claude Code documentation. I will run destroy myself.
- DEPLOY PAUSE: pause after PHASE 6 and wait for my explicit "deploy" command. Never git push, terraform apply or run az commands that create or change resources before that command. The only exception is the PHASE 0 feasibility tests: before creating any temporary test resource, tell me in Thai what you will create, wait for my OK, and delete it right after the test (prefer read-only az commands such as listing models, quotas and regions first).
- Never delete data or change RBAC outside Terraform unless I explicitly ask.
- Never ask me to paste credentials into the chat or into files. Use az login interactively.
- Keep everything idempotent and re-runnable.

## 13. Human-only steps

At the deployment phase give me ONE checklist in Thai with exact steps, then wait:
1. az login and select the Azure for Students subscription.
2. Confirm the region and AI provider from docs/feasibility.md.
3. Provide alert_email; confirm the action group email after apply.
4. Create the GitHub repo (empty), push, set repository variables from the bootstrap outputs.
5. Hugging Face login only if the download needs it.
Continue automatically after I confirm.

## 14. Phases (order of docs/spec/tasks.md)

0. Feasibility
1. Scaffolding: venv, requirements files, .gitignore, pyproject, ruff, pre-commit, scripts/tasks.py, .claude/settings.json
2. Data scripts and sample data, with tests
3. Application code (ingest, enrich, api, classifier) with unit tests
4. Terraform: bootstrap stack, then all modules and envs/dev; fmt, validate, tflint, checkov clean
5. CI/CD workflows
6. Web dashboard
   >>> DEPLOY PAUSE: wait for my "deploy" command <<<
7. Deploy: bootstrap apply, data upload, dev apply, function deploy, backfill 10 days, smoke test
8. Evaluation: run evaluate.py and commit docs/evaluation.md
9. Documentation: README, ADRs, runbook, cost, github-setup, module READMEs
10. Final verification against the Definition of Done

## 15. Definition of done

- [ ] lint and tests pass; coverage >= 80% for src/
- [ ] terraform fmt, validate, tflint and checkov pass for all stacks
- [ ] Dev environment deployed; the timer is active
- [ ] 10-day backfill processed; poison queue empty; smoke test passes
- [ ] Dashboard loads from the static website URL and shows real data
- [ ] docs/evaluation.md has real accuracy numbers; docs/feasibility.md has real check results
- [ ] README top section complete; all docs written; runbook contains real incidents from this build
- [ ] No secrets or subscription-specific values in git history
- [ ] CI and deploy workflows pass on GitHub

## 16. Final report (in Thai)

What was built, dashboard and API URLs, evaluation results, what each scripts/tasks.py subcommand does, how to pause or destroy to protect the remaining credit, remaining manual steps, and suggested resume bullets based on the actual results.
