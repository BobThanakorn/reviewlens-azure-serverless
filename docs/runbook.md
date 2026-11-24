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
