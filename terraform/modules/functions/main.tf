terraform {
  required_version = ">= 1.10"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.0, < 6.0"
    }
  }
}

# One Function App on Flex Consumption (scale-to-zero, no always-on cost) with its own
# user-assigned identity and its own storage account for the deployment package and host state.
#
# A user-assigned identity is used instead of a system-assigned one because Flex Consumption reads
# the deployment container while the app is being created: the identity and its role must
# exist first, and only a user-assigned identity can be created and authorised before the app.

locals {
  deployment_container = "app-package"
  storage_blob_url     = azurerm_storage_account.host.primary_blob_endpoint
}

resource "azurerm_user_assigned_identity" "app" {
  name                = "id-${var.app_name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_storage_account" "host" {
  #checkov:skip=CKV_AZURE_59:Public network access stays on: Functions and GitHub runners have no VNet; access needs Entra auth, shared keys are disabled and anonymous blob access is off
  #checkov:skip=CKV_AZURE_33:Queue request logging needs diagnostic settings and log ingestion cost; listed under production next steps
  #checkov:skip=CKV_AZURE_206:LRS is enough for a re-creatable dev environment; geo-replication would double storage cost
  #checkov:skip=CKV2_AZURE_1:Microsoft-managed keys are acceptable here; customer-managed keys need Key Vault, listed under production next steps
  #checkov:skip=CKV2_AZURE_33:Private endpoints add always-on hourly cost, which this project forbids
  name                = var.storage_account_name
  resource_group_name = var.resource_group_name
  location            = var.location

  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true

  blob_properties {
    delete_retention_policy {
      days = 7
    }

    container_delete_retention_policy {
      days = 7
    }
  }

  tags = var.tags
}

resource "azurerm_storage_container" "package" {
  #checkov:skip=CKV2_AZURE_21:Blob read logging needs diagnostic settings and log ingestion cost; listed under production next steps
  name                  = local.deployment_container
  storage_account_id    = azurerm_storage_account.host.id
  container_access_type = "private"
}

# Host storage (timer leases, queue trigger state) and the deployment package need blob owner
# and queue access on this account only.
resource "azurerm_role_assignment" "host_blob" {
  scope                = azurerm_storage_account.host.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "host_queue" {
  scope                = azurerm_storage_account.host.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_service_plan" "app" {
  #checkov:skip=CKV_AZURE_212:Flex Consumption scales to zero by design; a minimum instance count would add always-on cost
  #checkov:skip=CKV_AZURE_225:Zone redundancy is not available on the scale-to-zero plan and would add cost
  name                = "asp-${var.app_name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "FC1"
  tags                = var.tags
}

resource "azurerm_function_app_flex_consumption" "app" {
  name                = var.app_name
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = azurerm_service_plan.app.id

  runtime_name           = "python"
  runtime_version        = var.python_version
  maximum_instance_count = var.max_instances
  instance_memory_in_mb  = var.instance_memory_mb

  https_only                    = true
  public_network_access_enabled = true

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${local.storage_blob_url}${azurerm_storage_container.package.name}"
  storage_authentication_type       = "UserAssignedIdentity"
  storage_user_assigned_identity_id = azurerm_user_assigned_identity.app.id

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app.id]
  }

  site_config {
    minimum_tls_version                    = "1.2"
    http2_enabled                          = true
    application_insights_connection_string = var.application_insights_connection_string
  }

  app_settings = merge(
    {
      # Selects the user-assigned identity for DefaultAzureCredential in the Python code.
      AZURE_CLIENT_ID = azurerm_user_assigned_identity.app.client_id

      # Identity-based host storage (no connection string).
      AzureWebJobsStorage__accountName = azurerm_storage_account.host.name
      AzureWebJobsStorage__credential  = "managedidentity"
      AzureWebJobsStorage__clientId    = azurerm_user_assigned_identity.app.client_id
    },
    # Identity-based queue trigger connection named DataStorage. It is built here because it
    # needs this module's own client id, which callers cannot know in advance.
    var.data_queue_service_uri == "" ? {} : {
      DataStorage__queueServiceUri = var.data_queue_service_uri
      DataStorage__credential      = "managedidentity"
      DataStorage__clientId        = azurerm_user_assigned_identity.app.client_id
    },
    var.app_settings,
  )

  tags = var.tags

  depends_on = [
    azurerm_role_assignment.host_blob,
    azurerm_role_assignment.host_queue,
  ]

  lifecycle {
    # Code is published by scripts/deploy_functions.py, not by Terraform.
    ignore_changes = [zip_deploy_file]
  }
}
