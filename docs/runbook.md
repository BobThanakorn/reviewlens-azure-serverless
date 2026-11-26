# Runbook

Status: incidents 1-19 are real errors from this build. The procedures below were written after the first deployment; each one says whether it has been exercised on the live environment.

## Procedures

All commands are PowerShell. Names come from `terraform -chdir=terraform/envs/dev output`.

### Drain the poison queue
**Exercised:** the copy-back step (2026-11-26, after incident 15). The delete step is an owner action (the agent session is not allowed to delete queue messages).
1. Find the cause first: Application Insights `exceptions` for `Functions.enrich`, and peek the message (`peek_messages` does not dequeue it).
2. Deploy the fix.
3. Copy each poison message back to `enrich` with the same body (a base64 Event Grid event). The host reprocesses it; `enrich` skips any chunk whose processed blob already exists.
4. When `processed` has the expected blobs, delete the poison messages (the owner does this; it removes data). The smoke test requires an empty poison queue.

### Reprocess a day
**Partly exercised:** step 3 was used for the first chunk.
1. Delete the processed blob of that day, `processed/dt=YYYY-MM-DD/chunk-NNNNNN.jsonl` (owner action: it deletes data). `enrich` skips chunks that already have output, so this is what makes it run again.
2. The raw blob stays as it is.
3. Re-trigger: send the original Event Grid event for that raw blob to `enrich` (as in "Drain the poison queue"), or copy the raw blob over itself so storage raises a new `BlobCreated` event.

### Change the model
**Not exercised yet.**
1. Set `openai_model_name`, `openai_model_version` and, if needed, `openai_capacity` in `terraform/envs/dev/terraform.tfvars`, then `python scripts/tasks.py plan` and apply.
2. Plan for the deployment to be replaced, not updated in place: incident 7 showed that an in-place capacity change did not reach the gateway.
3. Check the `x-ratelimit-*` headers of one call, then run `python scripts/tasks.py deploy-functions` (it also removes the stray setting from incident 13) and a 1-day backfill as a canary.
4. Re-run `python scripts/tasks.py evaluate` and compare with `docs/evaluation.md`.

### Pause the daily timer
**Not exercised yet.** The timer `daily_ingest` runs at 01:00 UTC (08:00 Bangkok) and ingests one chunk a day until the 10 source chunks are used up; after that it only logs `end of data`.
- Microsoft documents disabling one function with the app setting `AzureWebJobs.daily_ingest.Disabled = true`. Add it through the `app_settings` input of `module.func_pipeline` so Terraform keeps it, then apply. Verify in the host log that the timer is no longer scheduled; the setting name format on Linux has not been verified on this app.
- To stop all cost from the pipeline, the stronger option is `terraform destroy` of `envs/dev` (owner only, see README "Cost and teardown").

## Incidents

### 1. `az` is not recognised
- **Symptom:** `az: The term 'az' is not recognized` in PowerShell; Phase 0 Azure checks cannot run.
- **Root cause:** Azure CLI was not installed (not on PATH, not in the standard install folders).
- **Fix:** `winget install -e --id Microsoft.AzureCLI`, open a **new** terminal (PATH is read at start), then `az login`.
- **Prevention:** the tool check is the first task in `docs/spec/tasks.md` (0.1) and its result is recorded in `docs/feasibility.md`.

### 2. `ModuleNotFoundError: No module named 'azure.core.match_conditions'`
- **Symptom:** importing `common.storage` failed during `pytest` collection.
- **Root cause:** `MatchConditions` is exported from the top-level `azure.core` package, not from a `match_conditions` submodule.
- **Fix:** `from azure.core import MatchConditions`.
- **Prevention:** every module that imports an Azure SDK symbol is imported by at least one unit test, so a wrong path fails in CI instead of at deploy time.

### 3. `pip check` reports conflicting `packaging` versions
- **Symptom:** `pytest 9.2.0 has requirement packaging>=24, but you have packaging 23.2`.
- **Root cause:** `checkov` pins an old `packaging` and was installed in the same virtual environment as the test tools. A first all-in-one `pip install` was also very slow (resolver backtracking).
- **Fix:** checkov now lives in its own environment (`.venv-checkov`, `requirements-checkov.txt`, run with `python scripts/tasks.py checkov`).
- **Prevention:** tools that pin shared libraries get their own venv; `pip check` is part of the local gate.

### 4. `ValueError: Function daily_ingest does not have a unique function name`
- **Symptom:** two unit tests failed when they both called `app.get_functions()`.
- **Root cause:** the Azure Functions SDK validates names on every call and rejects a second call on the same `FunctionApp` object. Not a bug in the app.
- **Fix:** the tests index each app once at module level and share the result.
- **Prevention:** a comment in `tests/test_function_apps.py` explains why.

### 5. azurerm provider is a new major version (5.x)
- **Symptom:** none yet; found while pinning versions (registry shows 5.15.0, the brief was written against 4.x).
- **Root cause:** major provider upgrade. Containers and queues take `storage_account_id` (management-plane), static website is a separate resource, and Flex Consumption uses `azurerm_function_app_flex_consumption`.
- **Fix:** resource arguments were read from the provider schema (`terraform providers schema -json`) instead of from memory.
- **Prevention:** `required_providers` pins exact versions; upgrades are a deliberate change.

### 6. `BadRequestError: Unsupported parameter: 'max_tokens'` from gpt-5
- **Symptom:** every classification failed with HTTP 400 `Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.`
- **Root cause:** `gpt-5-nano` is a reasoning model. It rejects `max_tokens` and any `temperature` other than the default. Unit tests with fake clients could not catch it.
- **Fix:** send `max_completion_tokens` (default 800) and no `temperature`; `reasoning_effort` is sent only when configured. Unit tests assert the exact request parameters.
- **Prevention:** the Phase 0 feasibility test runs the real classifier against a real deployment before anything else depends on it.

### 7. HTTP 429 although the deployment capacity was raised
- **Symptom:** `Your requests to gpt-5-nano for chat in southeastasia have exceeded request rate limit`; the headers showed `x-ratelimit-limit-requests: 1` and `x-ratelimit-limit-tokens: 1000` even after the deployment was updated to capacity 50.
- **Root cause:** `az cognitiveservices account deployment show` reported 50 (50 RPM, 50K TPM), but the gateway kept enforcing the capacity of the original deployment (1) for more than 5 minutes after an in-place update.
- **Fix:** delete the deployment and create it again with the target capacity; the new limits applied immediately. In Terraform, create it with the right `openai_capacity` from the start. If capacity must change on a live system, plan for a delete and create.
- **Prevention:** read the `x-ratelimit-*` response headers (they show the limit actually enforced), not only the control-plane value.

### 8. Azure OpenAI default reasoning is slow and token-hungry
- **Symptom:** 5 to 10 seconds and 950 to 1,725 output tokens per review, so a 50-review chunk would take several minutes.
- **Root cause:** gpt-5 models spend hidden reasoning tokens by default.
- **Fix:** `reasoning_effort=minimal` (needs API version `2025-04-01-preview`): 43 to 55 output tokens and 1.5 to 3.3 seconds.
- **Prevention:** `OPENAI_REASONING_EFFORT` and `OPENAI_API_VERSION` are app settings set by Terraform. Azure also reserves TPM quota from `max_completion_tokens`, so keep it small.

### 9. `az` works in PowerShell but not in the `!` prompt
- **Symptom:** `az: command not found`, then `'C:\Program' is not recognized` when a bash function pointed at `az.cmd`.
- **Root cause:** the `!` prefix runs in Git Bash, where the Windows Azure CLI is not on PATH, and Git Bash cannot call a `.cmd` in a path with spaces from a function.
- **Fix:** run Azure CLI commands in PowerShell (use `( )` instead of `$( )` for command substitution).
- **Prevention:** the deploy checklist uses PowerShell commands only.

### 10. Creating a role assignment from the agent session was blocked
- **Symptom:** the agent session refused `az role assignment create` even though the owner had approved the temporary test.
- **Root cause:** the Claude Code permission classifier treats RBAC changes as sensitive; the project rules also deny `az role assignment delete` and `az group delete`.
- **Fix:** the owner ran the one command in their own terminal. Cleanup relied on deleting the resource, which removes role assignments scoped to it. The empty temporary resource group is removed by the owner with `az group delete`.
- **Prevention:** keep RBAC in Terraform; for manual tests, ask the owner to run the single `az role assignment create`.

### 11. `MissingSubscriptionRegistration` on the first `terraform apply`
- **Symptom:** the apply of `envs/dev` stopped with `409 MissingSubscriptionRegistration: The subscription is not registered to use namespace 'Microsoft.Web'` (also `Microsoft.OperationalInsights`, `microsoft.insights`). 34 of 48 resources were already created.
- **Root cause:** a new Azure for Students subscription has only some resource providers registered, and the provider is configured with `resource_provider_registrations = "none"` (ADR 008). `terraform plan` does not ask ARM about registration, so it passed.
- **Fix:** register the providers once (`az provider register --namespace <name>`) for `Microsoft.Web`, `Microsoft.OperationalInsights`, `microsoft.insights`, `Microsoft.EventGrid` and `Microsoft.AlertsManagement`, wait until `registrationState` is `Registered`, then plan and apply again. Terraform created only the 15 missing resources; nothing was deleted.
- **Prevention:** the deploy checklist (task 7.0) lists provider registration; check `az provider show -n <ns> --query registrationState` before the first apply.

### 12. Event Grid subscription: `Managed Identity Authorization Error`
- **Symptom:** creating `raw-jsonl-to-enrich-queue` failed three times over more than 10 minutes with `Managed identity for event subscription does not have authorization to deliver to the endpoint`.
- **Root cause:** the role `Storage Queue Data Message Sender` was assigned to the topic identity on the `enrich` queue only. Read-only checks showed the assignment existed and matched the topic's principal, so it was not RBAC propagation. Event Grid expects the role on the storage account (ADR 009).
- **Fix:** scope the role assignment to the data storage account in `modules/eventing`; Terraform replaced the assignment and the subscription was created at the first attempt.
- **Prevention:** do not retry the same apply hoping for propagation; after one retry, compare the role scope with the service documentation.

### 13. Host unhealthy, `config-zip` exits 3 and function keys cannot be read
- **Symptom:** `ERROR: Failed to fetch host key to check for function app status` (exit code 3) after `Deployment endpoint responded with status code 202`; `az functionapp keys list` returned `Bad Request`. Application Insights showed `There was an error performing a read operation on the Blob Storage Secret Repository` with `403 Server failed to authenticate the request ... signature`, and the health check `azure.functions.webjobs.storage` was `Unhealthy` on both apps.
- **Root cause:** the app had a bare `AzureWebJobsStorage` setting, a connection string with an **empty** `AccountKey`, next to the identity settings `AzureWebJobsStorage__accountName/__clientId/__credential`. Terraform never set it and it is not in the plan or state. This is a known azurerm bug (hashicorp/terraform-provider-azurerm#29149): the flex consumption resource adds it on apply. The host prefers the connection string, signs with the empty key, and the account has shared-key access disabled, so every storage call returns 403. A first workaround that tolerated exit code 3 was wrong (it hid this cause) and was reverted.
- **Fix:** delete the setting (`az functionapp config appsettings delete --setting-names AzureWebJobsStorage`). `scripts/deploy_functions.py` now does this for each app before publishing, so it also runs in CI after every apply. The deploy then exits 0 and `keys list` works.
- **Prevention:** after any `terraform apply` that touches a function app, run the deploy script (it re-cleans the setting). Check `az functionapp config appsettings list` for a bare `AzureWebJobsStorage` when you see 403 `signature` errors from the host.

### 14. HTTP function listed but returns 404: route conflicts with a built-in route
- **Symptom:** `POST /api/admin/backfill` returned an empty 404 even with a valid function key, while `az functionapp function list` showed `backfill`. Application Insights: `The 'backfill' function is in error: The specified route conflicts with one or more built in routes` and `No HTTP routes mapped`.
- **Root cause:** the `admin/` prefix is reserved by the Functions host (`/admin/host/...`). The worker registers the function, the host refuses to serve it.
- **Fix:** route renamed to `ops/backfill` (`src/pipeline/function_app.py`, `scripts/smoke_test.py`). A unit test now rejects any HTTP route that starts with `admin` or `runtime`.
- **Prevention:** a listed function is not proof it is served; after deploy read the host log (`traces`) for "is in error" and call the route once.

### 15. `enrich` fails with `JSONDecodeError` and messages land in the poison queue
- **Symptom:** the first backfill chunk raised a BlobCreated event, Event Grid delivered it to the `enrich` queue, `Functions.enrich` failed three times in milliseconds with `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` and the message moved to `enrich-poison`.
- **Root cause:** Event Grid writes the event to a Storage queue as **base64 text** (`eyJ0b3BpYyI6...` is `{"topic":...`). `host.json` set `messageEncoding: none` on the wrong assumption of plain JSON, so the handler received base64. Unit tests built messages by hand as plain JSON and could not catch it.
- **Fix:** `messageEncoding` is `base64` (the default) so the host decodes the message first; the test and ADR 002 were corrected.
- **Prevention:** peek a real message (`peek_messages` does not dequeue) before fixing a trigger assumption; the first real event is the integration test for the queue format.

### 16. Workflows defaulted to the wrong AI provider
- **Symptom:** none in production; found while setting GitHub variables before the first push. `ci.yml`, `deploy.yml` and `destroy.yml` used `vars.CLASSIFIER_PROVIDER || 'language'`.
- **Root cause:** the fallback was written before ADR 000 chose `openai`. With the variable unset, the first CI apply would have switched the provider and replaced the OpenAI account with a Language account.
- **Fix:** the fallback is `openai` (same as the Terraform default), and `docs/github-setup.md` says to set the variable explicitly.
- **Prevention:** compare every workflow default with the Terraform variable default when a decision changes.

### 17. `python scripts/tasks.py checkov` fails with `No module named 'checkov'`
- **Symptom:** `File association not found for extension .py`, then `ModuleNotFoundError: No module named 'checkov'` from `.venv-checkov\Scripts\checkov.cmd`.
- **Root cause:** on Windows the `checkov.cmd` launcher starts the Python registered for `.py` files, not the interpreter of `.venv-checkov`.
- **Fix:** `tasks.py` runs `<venv python> -m checkov.main`. Result after the Phase 7 Terraform changes: 62 passed, 0 failed, 40 skipped (each skip justified inline).
- **Prevention:** call tools through a specific interpreter (`python -m ...`) instead of generated launchers.

### 18. `azure/login` fails with `AADSTS700213: No matching federated identity record`
- **Symptom:** the first Deploy run failed at `azure/login`; every later step was skipped. The token's subject was `repo:<owner>@<owner id>/<repo>@<repo id>:ref:refs/heads/main`.
- **Root cause:** repositories created recently carry immutable numeric ids in the OIDC subject. The federated credentials expected the plain `repo:<owner>/<repo>:...` form, so Entra found no match.
- **Fix:** new bootstrap variable `github_oidc_repo` (`owner@<id>/repo@<id>`, from `gh api repos/<owner>/<repo>`); `terraform apply` updated the two credentials in place (0 add, 2 change, 0 destroy).
- **Prevention:** read the `subject claim` line of a failed `azure/login` log, and compare it with `az identity federated-credential list` before the first push.

### 19. `Terraform plan` on a pull request fails with 403 `AuthorizationFailed`
- **Symptom:** the first PR's `plan` job failed: `does not have authorization to perform action 'Microsoft.Web/sites/config/list/action'` (both Function Apps) and `'Microsoft.EventGrid/systemTopics/eventSubscriptions/getFullUrl/action'`.
- **Root cause:** the read-only plan identity had the built-in Reader role. Reader covers GET reads but not the POST "list" actions that Terraform calls while refreshing app settings and the Event Grid delivery URL. Not visible from the code; only a real PR run shows it.
- **Fix:** custom role `rl-plan-refresh` with exactly those two actions, assigned on the dev resource group only (bootstrap stack, `azurerm_role_definition.plan_refresh`).
- **Trade-off:** `config/list/action` lets a same-repository pull request read the app settings. They hold only account names and client ids, no secrets. Fork pull requests do not run the plan job.
- **Prevention:** run the plan job once on a real PR before relying on it; add actions one at a time from the error text, never widen to Contributor.
