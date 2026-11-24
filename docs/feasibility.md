# Feasibility (Phase 0)

Status: IN PROGRESS. Only section 0 has real results. Everything else is pending until Azure CLI is installed. No value in this file is assumed or invented.

## 0. Local tools (checked 2026-11-25)

| Tool | Result |
|---|---|
| git | 2.54.0.windows.1 |
| terraform | v1.17.2 (brief needs >= 1.10) |
| python | 3.12.10 |
| PowerShell | 7.7.0 |
| gh | present |
| az (Azure CLI) | **NOT FOUND** (not on PATH, not in standard install folders) |
| tflint | **NOT FOUND** (needed for CI; optional locally) |

Install Azure CLI: `winget install -e --id Microsoft.AzureCLI`, then open a new terminal, run `az login`.

## 1. Subscription, regions, resource providers
PENDING (needs `az`).

## 2. Functions hosting plans in the chosen region
PENDING.

## 3. Azure OpenAI / Foundry (models, quota, Thai test)
PENDING.

## 4. Azure AI Language sentiment with Thai text
PENDING (only if section 3 fails).

## 5. Consumption budget support
PENDING.

## Decision
PENDING. Will be recorded in `docs/adr/000-ai-provider.md`.
