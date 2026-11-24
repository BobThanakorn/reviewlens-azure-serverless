data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  state_account_name = "st${var.name_prefix}tf${random_string.suffix.result}"
  state_container    = "tfstate"

  # ARM id of the state container, used as an exact role-assignment scope.
  state_container_scope = "${azurerm_storage_account.state.id}/blobServices/default/containers/${local.state_container}"
  app_rg_scope          = azurerm_resource_group.app.id

  github_issuer   = "https://token.actions.githubusercontent.com"
  github_audience = ["api://AzureADTokenExchange"]

  # Role definition ids (GUIDs) the apply identity may hand out inside the app resource group.
  # Anything else is refused by the ABAC condition below, so a compromised pipeline cannot
  # grant itself Owner. Verify with: az role definition list --name "<role name>" --query [].name
  assignable_role_ids = [
    "ba92f5b4-2d11-453d-a403-e96b0029c9fe", # Storage Blob Data Contributor
    "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1", # Storage Blob Data Reader
    "974c5e8b-45b9-4653-ba55-5f855dd0fb88", # Storage Queue Data Contributor
    "c6a89b2d-59bc-44d0-9896-0f6e12d7b80a", # Storage Queue Data Message Sender
    "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd", # Cognitive Services OpenAI User
    "a97b65f3-24c7-4388-baec-2e87135dc908", # Cognitive Services User
  ]
  assignable_ids_csv = join(", ", local.assignable_role_ids)

  uaa_condition = <<-EOT
    (
     (
      !(ActionMatches{'Microsoft.Authorization/roleAssignments/write'})
     )
     OR
     (
      @Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.assignable_ids_csv}}
     )
    )
    AND
    (
     (
      !(ActionMatches{'Microsoft.Authorization/roleAssignments/delete'})
     )
     OR
     (
      @Resource[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAnyValues:GuidEquals {${local.assignable_ids_csv}}
     )
    )
  EOT
}

# ---------------------------------------------------------------- resource groups

resource "azurerm_resource_group" "state" {
  name     = var.state_resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_resource_group" "app" {
  name     = var.app_resource_group_name
  location = var.location
  tags     = var.tags
}

# ---------------------------------------------------------------- Terraform state

#checkov:skip=CKV_AZURE_206:LRS is enough for a portfolio project; state is versioned and soft-deleted
#checkov:skip=CKV_AZURE_59:Public network access stays on so GitHub-hosted runners can reach the state; access needs Entra auth
#checkov:skip=CKV2_AZURE_1:Microsoft-managed keys are acceptable here; CMK is listed under production next steps
#checkov:skip=CKV2_AZURE_33:No private endpoint: it would add always-on cost
#checkov:skip=CKV_AZURE_33:Queue logging is irrelevant, this account has no queues
#checkov:skip=CKV2_AZURE_21:Blob read logging needs a log workspace that does not exist yet at bootstrap time
resource "azurerm_storage_account" "state" {
  name                = local.state_account_name
  resource_group_name = azurerm_resource_group.state.name
  location            = azurerm_resource_group.state.location

  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 14
    }

    container_delete_retention_policy {
      days = 14
    }
  }

  tags = var.tags
}

resource "azurerm_storage_container" "state" {
  name                  = local.state_container
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
}

# Whoever runs the bootstrap needs data access to use the remote backend afterwards.
resource "azurerm_role_assignment" "state_admin" {
  scope                = local.state_container_scope
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id

  depends_on = [azurerm_storage_container.state]
}

# ---------------------------------------------------------------- GitHub OIDC identities

resource "azurerm_user_assigned_identity" "plan" {
  name                = "id-${var.name_prefix}-gh-plan"
  resource_group_name = azurerm_resource_group.state.name
  location            = azurerm_resource_group.state.location
  tags                = var.tags
}

resource "azurerm_user_assigned_identity" "apply" {
  name                = "id-${var.name_prefix}-gh-apply"
  resource_group_name = azurerm_resource_group.state.name
  location            = azurerm_resource_group.state.location
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "plan" {
  name                      = "github-pull-request"
  user_assigned_identity_id = azurerm_user_assigned_identity.plan.id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "repo:${var.github_repo}:pull_request"
}

resource "azurerm_federated_identity_credential" "apply" {
  name                      = "github-main"
  user_assigned_identity_id = azurerm_user_assigned_identity.apply.id
  issuer                    = local.github_issuer
  audience                  = local.github_audience
  subject                   = "repo:${var.github_repo}:ref:refs/heads/main"
}

# ---- plan identity: read-only. `terraform plan -lock=false` is used in CI because taking the
# state lease needs write access (see docs/adr/004-github-oidc-managed-identity.md).

resource "azurerm_role_assignment" "plan_reader" {
  scope                = local.app_rg_scope
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.plan.principal_id
}

resource "azurerm_role_assignment" "plan_state_reader" {
  scope                = local.state_container_scope
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_user_assigned_identity.plan.principal_id

  depends_on = [azurerm_storage_container.state]
}

# ---- apply identity: Contributor + a constrained User Access Administrator, app RG only.

resource "azurerm_role_assignment" "apply_contributor" {
  scope                = local.app_rg_scope
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.apply.principal_id
}

resource "azurerm_role_assignment" "apply_uaa" {
  scope                = local.app_rg_scope
  role_definition_name = "User Access Administrator"
  principal_id         = azurerm_user_assigned_identity.apply.principal_id
  principal_type       = "ServicePrincipal"
  condition_version    = "2.0"
  condition            = local.uaa_condition
}

resource "azurerm_role_assignment" "apply_state_contributor" {
  scope                = local.state_container_scope
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.apply.principal_id

  depends_on = [azurerm_storage_container.state]
}
