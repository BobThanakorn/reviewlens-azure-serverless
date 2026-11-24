# ADR 008: azurerm provider 5.x conventions

Status: Accepted

## Context
The brief was written against azurerm 4.x. The registry's latest stable provider is **5.15.0** (checked 2026-11-25), and the brief says to follow current docs when they differ.

## Decision
Pin `azurerm = 5.15.0`, `random = 3.9.1`, `local = 2.9.1` in root configurations (modules use ranges). Resource shapes were read from `terraform providers schema -json`, which showed:
- `azurerm_storage_container` and `azurerm_storage_queue` take `storage_account_id` (management plane), so they work with shared-key access disabled.
- Static website is its own resource, `azurerm_storage_account_static_website`.
- Flex Consumption is `azurerm_function_app_flex_consumption`, with `storage_authentication_type = "UserAssignedIdentity"`.
- `resource_provider_registrations = "none"`: the CI identities cannot register providers (subscription scope), so a human registers them once.
- `storage_use_azuread = true` for the few data-plane operations.

## Consequences
- Upgrades are deliberate; `.terraform.lock.hcl` is committed.
- Static website provisioning and `$web` uploads with shared keys disabled are **unverified until the first deploy**; the fallback is enabling shared-key access on the web account only (documented in the runbook if needed).
- Budget, Event Grid queue delivery with managed identity and the workbook JSON also get their first real test at deploy.
