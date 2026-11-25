# Tasks

Current phase: **DEPLOY PAUSE reached (Phases 1-6 done locally).** Phase 0 is complete (provider: openai, gpt-5-nano, southeastasia). Wait for the user's "deploy".
Status: DRAFT plan, awaiting approval. Tick a task only after its **Verify** step passes, then commit (Conventional Commits).
Guard rails: DEPLOY PAUSE after Phase 6. No `git push`, `terraform apply` or resource-changing `az` command before the user writes "deploy". Max 20 reviews through a real classifier during development.

## Phase 0. Feasibility (read-only first)

- [x] 0.1 Check tools: git 2.54, terraform 1.17.2, python 3.12.10, PowerShell 7.7, gh present. **Missing: az, tflint.**
  Verify: output recorded in `docs/feasibility.md`.
- [x] 0.2 User installs Azure CLI (`winget install -e --id Microsoft.AzureCLI`), reopens the terminal, runs `az login` and selects the Students subscription.
  Verify: `az version` works; `az account show` shows the subscription name (shown to the user before anything else).
- [x] 0.3 Subscription type, allowed regions (Azure Policy "Allowed resource deployment regions"), registered resource providers. Read-only. Never write the subscription ID into a file.
  Verify: `docs/feasibility.md` section 1 filled with real output (ID masked).
- [x] 0.4 Functions hosting availability in the chosen region (Flex Consumption vs Consumption), plus Python runtime version and Flex timer/time-zone behaviour in current docs.
  Verify: section 2 filled; region chosen.
- [x] 0.5 Azure OpenAI/Foundry: list models and quota in the region (read-only). Only with user OK per resource: create a temporary account, try a small deployment and one Thai review, delete immediately.
  Verify: section 3 has real result (success or exact error code, e.g. RequestDisallowedByAzure); `az resource list` confirms no leftovers.
- [x] 0.6 If 0.5 fails: Azure AI Language sentiment with a Thai text (confirm Thai support in current docs; prefer the free tier; same ask-first/delete rule).
  Verify: section 4 filled.
- [x] 0.7 Consumption budget support check (read-only).
  Verify: section 5 filled.
- [x] 0.8 Decide provider (`openai` | `language`), write `docs/adr/000-ai-provider.md`; report to the user in Thai.
  Verify: ADR exists; `docs/feasibility.md` complete.

## Phase 1. Scaffolding

- [x] 1.1 `git init`, `.gitignore` (.terraform/, *.tfstate*, *.tfvars, .env, .venv/, local.settings.json, coverage), LICENSE (MIT), initial commit.
  Verify: `git status` clean; `git check-ignore` confirms ignore rules.
- [x] 1.2 Create `.venv`, `requirements.txt` (pinned runtime deps), `requirements-dev.txt` (pytest, pytest-cov, ruff, checkov, pre-commit).
  Verify: `.venv\Scripts\python -m pip check` passes; no global installs.
- [x] 1.3 `pyproject.toml` (ruff, pytest, coverage `--cov=src --cov-fail-under=80`), `.pre-commit-config.yaml`.
  Verify: `ruff check .` and `pytest` run (empty suite allowed at this stage).
- [ ] 1.4 `.claude/settings.json` deny rules (terraform destroy, az group delete, az role assignment delete, git push --force, and PowerShell variants) using the current permission syntax from the Claude Code docs.
  Verify: JSON is valid and the syntax is confirmed against the docs. **Open:** rules written from memory of the current syntax (`Bash(cmd *)`); confirm against the Claude Code docs.
- [x] 1.5 `scripts/tasks.py` runner with subcommands: init, fmt, lint, test, plan, deploy, deploy-functions, bootstrap-data, backfill, smoke-test, evaluate, destroy (destroy only prints the instructions; the user runs it).
  Verify: `python scripts/tasks.py --help` lists all; `lint` and `test` subcommands run.
- [x] 1.6 Skeleton dirs and `docs/adr/` template. Commit.
  Verify: tree matches section 9 of the brief.

## Phase 2. Data scripts and sample data

- [x] 2.1 `scripts/bootstrap_data.py`: download, drop empty, sample 500 (seed 42), assign `review_id`, chunk by 50, upload with `DefaultAzureCredential`, `--dry-run` writes locally instead of uploading.
  Verify: unit tests with a fake dataset and fake blob client; dry-run produces 10 chunks; reruns are byte-identical.
- [x] 2.2 `sample-data/sample.jsonl` (20 rows, the only dataset content in git).
  Verify: 20 lines, valid schema, test loads it.
- [x] 2.3 Add the dataset credit and license note to a README stub.
  Verify: text present.

## Phase 3. Application code (TDD, mocks only)

- [x] 3.1 `src/common`: config, logging (JSON), models, storage helpers (blob read/write, ETag state, queue).
  Verify: unit tests incl. 412 handling.
- [x] 3.2 `src/common/classifier.py`: interface, OpenAI + Language implementations, keyword topic table, validation, re-ask, backoff on 429, factory by `CLASSIFIER_PROVIDER`.
  Verify: tests for valid, invalid-then-valid, invalid-twice, 429 retries (max 5), bad provider.
- [x] 3.3 `src/pipeline/enrich/prompt.py`: system prompt + 3 hand-written few-shot examples.
  Verify: test checks the prompt contains the schema and the examples are not dataset rows.
- [x] 3.4 `src/pipeline/ingest`: timer handler, backfill handler with validation, ETag state, end-of-data.
  Verify: tests for normal, concurrent 412, exhausted chunks, bad `backfill_days`, date range.
- [x] 3.5 `src/pipeline/enrich`: queue handler (parse Event Grid event, skip if processed exists, classify, write processed blob, logs).
  Verify: tests for happy path, skip, invalid output, error propagation to poison.
- [x] 3.6 `src/pipeline/function_app.py` + `host.json` (queue batchSize 1, newBatchThreshold 0, maxDequeueCount 3, messageEncoding none, function timeout).
  Verify: import test; host.json asserted by a test.
- [x] 3.7 `src/api`: aggregation, validation, 4 routes, CORS, de-dup, error JSON; `function_app.py`.
  Verify: tests for each route, whitelist violations, empty data, confusion matrix correctness.
- [x] 3.8 Local smoke of classifier against `sample-data/sample.jsonl` (<= 20 reviews) **only after the user confirms** and only if a provider exists. **Waiting on Phase 0 (provider) and the user's OK.**
  Verify: output logged; token usage noted.
- [x] 3.9 Quality gate.
  Verify: `ruff check`, `pytest` coverage >= 80% for `src/`.

## Phase 4. Terraform

- [x] 4.1 `terraform/bootstrap`: RGs, state storage (versioned, TLS-only, Entra auth), 2 UAMIs, federated credentials, role assignments, outputs (client IDs, tenant, subscription).
  Verify: `terraform fmt -check`, `terraform init -backend=false`, `terraform validate`.
- [x] 4.2 `modules/storage` (data + web accounts, containers, queues, soft delete, README).
  Verify: fmt, validate.
- [x] 4.3 `modules/functions` (two apps, plan, identities, app settings, role assignments, README).
  Verify: fmt, validate.
- [x] 4.4 `modules/eventing` (system topic, subscription with subject filter, MI delivery role, README).
  Verify: fmt, validate.
- [x] 4.5 `modules/monitoring` (workspace, App Insights, action group, 3 alerts, workbook, budget if supported, README).
  Verify: fmt, validate.
- [x] 4.6 `modules/web` (static website, `config.js` render, README).
  Verify: fmt, validate.
- [x] 4.7 `envs/dev` (main, backend, variables, outputs, `terraform.tfvars.example`).
  Verify: fmt, `init -backend=false`, validate.
- [x] 4.8 tflint (azurerm ruleset) and checkov clean; each skip justified inline. Install tflint locally if the user agrees.
  Verify: both exit 0.
- [x] 4.9 ADRs 001-006 and any changed decision (section 11 of design.md).
  Verify: files exist and are linked from the design.

## Phase 5. CI/CD

- [x] 5.1 `ci.yml` (as in design section 10).
  Verify: YAML parses and `tests/test_workflows.py` pins the security properties (actionlint not installed; run it in CI later).
- [x] 5.2 `deploy.yml`, `destroy.yml` (confirm gate).
  Verify: YAML lint; the confirm gate reviewed.
- [x] 5.3 `scripts/deploy_functions.py`, `scripts/smoke_test.py`, `scripts/evaluate.py` with unit tests.
  Verify: tests pass; smoke test supports `--dry-run`.
- [x] 5.4 `docs/github-setup.md`.
  Verify: lists variables and topics.

## Phase 6. Web dashboard

- [x] 6.1 `web/index.html`, `web/app.js`, `web/config.js.example` (Chart.js from CDN with pinned version + SRI).
  Verify: ran `scripts/dev_server.py` (real API code, mock data) and screenshotted it in headless Edge; `tests/test_web.py` forbids `innerHTML`, inline scripts and unpinned Chart.js.
- [x] 6.2 Accessibility and error-state check (empty data, API down).
  Verify: loading, missing-config and populated states checked by screenshot; 390 px layout stacks to one column. Not tested: API returning errors for one panel only (code path exists).
- [x] 6.3 Full local gate: ruff, pytest, terraform fmt/validate for all stacks, tflint, checkov.
  Verify: all green; `docs/spec/tasks.md` updated.

>>> **DEPLOY PAUSE**: stop and wait for the user's "deploy". <<<

## Phase 7. Deploy (after "deploy")

- [ ] 7.0 Human checklist in Thai (az login, region and provider confirm, `alert_email`, GitHub repo + variables, provider registration, Hugging Face login only if needed). Wait for confirmation.
- [ ] 7.1 `az account show`, show the subscription name.
- [ ] 7.2 Bootstrap apply (plan shown first, wait for confirmation, flag recurring cost).
- [ ] 7.3 `bootstrap_data.py` upload (500 reviews, 10 chunks).
- [ ] 7.4 `envs/dev` plan → confirmation → apply.
- [ ] 7.5 Deploy function code, upload web.
- [ ] 7.6 Backfill 10 days; poison queue empty.
- [ ] 7.7 `smoke_test.py` passes; dashboard URL opens with real data.
  Verify each step by its own output; log every real error to the runbook.

## Phase 8. Evaluation
- [ ] 8.1 `evaluate.py` run; commit `docs/evaluation.md` with real numbers. Verify: file has sample size, accuracy, matrix, 5 examples.

## Phase 9. Documentation
- [ ] 9.1 README top section (title, tagline, CI badge, Mermaid, skills table, results), prerequisites, quickstart, how it works, cost/teardown, dataset credit, next steps.
- [ ] 9.2 `docs/architecture.md`, `runbook.md` (real incidents + procedures), `cost.md` (no invented prices).
- [ ] 9.3 Module READMEs complete.
  Verify: links resolve; no secrets or IDs in any doc (grep for GUID patterns and the e-mail).

## Phase 10. Final verification
- [ ] 10.1 Walk the Definition of Done (brief section 15) item by item.
- [ ] 10.2 Secret scan of the working tree and git history.
- [ ] 10.3 Final report in Thai (brief section 16).
