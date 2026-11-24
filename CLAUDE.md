# ReviewLens (reviewlens-azure-serverless)

Serverless data and AI pipeline on Azure (Azure Functions, Storage, Event Grid, Terraform, GitHub Actions). Portfolio project for a junior Cloud Engineer role.

## Source of truth
- `docs/PROJECT_BRIEF.md` is the full spec. Re-read the section for the current phase before starting it.
- Progress lives in `docs/spec/tasks.md`. Tick tasks as they finish and commit.
- Before any phase, check which phase `docs/spec/tasks.md` says we are in.

## Language
- Reply to me in Thai.
- Code, comments, docs, commit messages (Conventional Commits) and ADRs in English.

## Environment
- Windows 11 + PowerShell 7. No bash or make assumptions locally.
- Helper scripts are Python (`scripts/tasks.py`, `smoke_test.py`, `deploy_functions.py`, `bootstrap_data.py`, `evaluate.py`).
- Always use the `.venv` virtual environment for Python packages. Never run a global `pip install`.
- `requirements.txt` = Function App runtime deps; `requirements-dev.txt` = dev tools.

## Critical rules
- Subscription is Azure for Students (USD 100 credit, no payment method). Never upgrade it or add a payment method.
- Never commit secrets, subscription/tenant IDs, emails, tfvars or state files.
- Never run `terraform destroy`, delete resource groups or data, or change RBAC outside Terraform unless I explicitly ask.
- Show the `terraform plan` summary and wait for my confirmation before the first `terraform apply`.
- Run `az account show` and show me the subscription name before any Azure action.
- DEPLOY PAUSE: stop after the dashboard phase (Phase 6). Do not push, apply or create Azure resources until I write "deploy". Only exception: Phase 0 feasibility tests, and only after I OK each temporary resource (delete it right after).
- Cost control: 500 reviews total, 10-day backfill, at most 20 reviews through the classifier during development.
- I do `az login` myself. Never ask me to paste credentials, keys or tokens into chat or files.
- No always-on-cost resources (VMs, AKS, fixed-SKU App Service Plans, Front Door, etc.).
- Keep everything idempotent. Record significant decisions as ADRs in `docs/adr/`.
- If this brief conflicts with current Azure/Terraform docs, follow the docs and record the change in an ADR.

## Quality gates before committing
`ruff check`, `pytest` (coverage >= 80% for src/), `terraform fmt -check` and `terraform validate` for any Terraform change.
