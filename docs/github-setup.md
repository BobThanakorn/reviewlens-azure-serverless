# GitHub setup

Everything here is set by you in the GitHub UI or with `gh`. Nothing in this file contains a real value; copy them from the bootstrap outputs (`terraform -chdir=terraform/bootstrap output`).

## Repository

- **Description:** Serverless data and AI pipeline on Azure: ingests Thai restaurant reviews daily, classifies them with an LLM, serves analytics on a dashboard. Terraform + GitHub Actions.
- **Topics:** `azure`, `terraform`, `serverless`, `infrastructure-as-code`, `data-pipeline`, `azure-functions`, `github-actions`
- **Branch protection on `main`:** require the `CI` workflow checks (Lint and test, Terraform checks, Terraform plan) and require pull requests. Deploy only runs on pushes to `main`, and the OIDC subject of the apply identity is bound to that branch.

## Repository variables (Settings > Secrets and variables > Actions > Variables)

| Variable | Source | Used by |
|---|---|---|
| `AZURE_CLIENT_ID_PLAN` | bootstrap output `client_id_plan` | ci.yml (plan, read-only) |
| `AZURE_CLIENT_ID_APPLY` | bootstrap output `client_id_apply` | deploy.yml, destroy.yml |
| `AZURE_TENANT_ID` | bootstrap output `tenant_id` | all Azure workflows |
| `AZURE_SUBSCRIPTION_ID` | bootstrap output `subscription_id` | all Azure workflows |
| `AZURE_LOCATION` | your allowed region (docs/feasibility.md) | Terraform `location` |
| `TFSTATE_RESOURCE_GROUP` | bootstrap output `state_resource_group_name` | Terraform backend |
| `TFSTATE_STORAGE_ACCOUNT` | bootstrap output `state_storage_account_name` | Terraform backend |
| `CLASSIFIER_PROVIDER` (optional) | `openai` or `language`, default `language` | Terraform |
| `ENABLE_BUDGET` (optional) | `true` only if budgets work on your subscription, default `false` | Terraform |
| `SMOKE_BACKFILL_DAYS` (optional) | default `3` | smoke test |

None of these is a credential: the workflows log in with short-lived OIDC tokens.

## Repository secrets

These are not credentials either, but they identify you, so they are kept out of the public variable list:

| Secret | Value |
|---|---|
| `ALERT_EMAIL` | address that receives alerts (Terraform `alert_email`) |
| `DATA_ADMIN_OBJECT_IDS` | JSON list such as `["<your user object id>", "<principal_id_apply>"]`. The apply identity needs data access so the smoke test can read blobs and the poison queue |

## First-time order

1. Run `terraform/bootstrap` locally once (see the Phase 7 checklist in `docs/spec/tasks.md`).
2. Create the empty GitHub repository, push, and add the variables and secrets above.
3. Open a pull request: CI runs the checks and posts the plan.
4. Merge: Deploy applies, publishes the apps and the dashboard, and runs the smoke test.

## Cost notes

- Each push to `main` runs the smoke test, which asks the pipeline to ingest `SMOKE_BACKFILL_DAYS` chunks (50 reviews each) until the 10 source chunks are used up. After that the backfill ingests nothing and the smoke test only checks the existing data. Set `SMOKE_BACKFILL_DAYS` to `0` to skip the backfill entirely.
- `destroy.yml` removes only `terraform/envs/dev`. It requires typing `destroy`; any other value skips the job.
