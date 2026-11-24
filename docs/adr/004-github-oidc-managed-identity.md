# ADR 004: GitHub OIDC through user-assigned managed identities

Status: Accepted

## Context
CI must run Terraform without stored secrets. An Azure for Students account may not be allowed to create Entra app registrations.

## Decision
Two **user-assigned managed identities** with GitHub federated credentials, created by `terraform/bootstrap`:

| Identity | Federated subject | Roles |
|---|---|---|
| plan | `repo:<owner/repo>:pull_request` | Reader on the app RG; Storage Blob Data Reader on the state container |
| apply | `repo:<owner/repo>:ref:refs/heads/main` | Contributor on the app RG; constrained User Access Administrator on the app RG; Storage Blob Data Contributor on the state container |

Two refinements to the brief:
1. **`terraform plan -lock=false` in pull requests.** The azurerm backend takes a blob lease to lock state, which needs write access. Giving PR runs write access to state is worse than skipping the lock for a read-only plan.
2. **ABAC condition on User Access Administrator.** The apply identity may only create or delete role assignments for a fixed list of role definition ids (storage data roles, Cognitive Services User/OpenAI User). A compromised pipeline therefore cannot grant itself Owner.

The identities live in the state resource group, so destroying the app resource group does not remove the ability to rebuild it.

## Consequences
- No client secrets in GitHub; tokens are short-lived and bound to repository and branch.
- Forked pull requests do not receive OIDC tokens, so plans only run for same-repo PRs.
- New roles used by Terraform must be added to `assignable_role_ids` in `terraform/bootstrap/main.tf` (apply fails with an authorization error otherwise). The ids must be verified with `az role definition list` before the first deploy.
