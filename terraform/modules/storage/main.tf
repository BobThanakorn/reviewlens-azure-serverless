terraform {
  required_version = ">= 1.10"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.0, < 6.0"
    }
  }
}

locals {
  account_id = azurerm_storage_account.data.id
}

resource "azurerm_storage_account" "data" {
  #checkov:skip=CKV_AZURE_59:Public network access stays on: Functions and GitHub runners have no VNet; access needs Entra auth, shared keys are disabled and anonymous blob access is off
  #checkov:skip=CKV_AZURE_33:Queue request logging needs diagnostic settings and log ingestion cost; listed under production next steps
  #checkov:skip=CKV_AZURE_206:LRS is enough for a re-creatable dev environment; geo-replication would double storage cost
  #checkov:skip=CKV2_AZURE_1:Microsoft-managed keys are acceptable here; customer-managed keys need Key Vault, listed under production next steps
  #checkov:skip=CKV2_AZURE_33:Private endpoints add always-on hourly cost, which this project forbids
  name                = var.account_name
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

resource "azurerm_storage_container" "this" {
  #checkov:skip=CKV2_AZURE_21:Blob read logging needs diagnostic settings and log ingestion cost; listed under production next steps
  for_each = toset(var.containers)

  name                  = each.value
  storage_account_id    = local.account_id
  container_access_type = "private"
}

resource "azurerm_storage_queue" "this" {
  for_each = toset(var.queues)

  name               = each.value
  storage_account_id = local.account_id
}
