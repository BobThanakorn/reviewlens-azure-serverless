# Runbook

Status: incidents are added as they happen during the build. Operating procedures (reprocess a day, drain the poison queue, change model, pause the timer) are written in Phase 9 after the first deployment, so they are tested before they are documented.

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
