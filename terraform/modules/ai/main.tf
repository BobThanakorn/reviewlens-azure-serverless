terraform {
  required_version = ">= 1.10"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.0, < 6.0"
    }
  }
}

# One AI account, shaped by `provider_kind`:
#   openai   -> Azure OpenAI account + one chat model deployment
#   language -> Azure AI Language (sentiment analysis); free F0 tier by default
# Keys are disabled: callers authenticate with Entra ID (managed identity), which requires the
# custom sub-domain below.

locals {
  is_openai = var.provider_kind == "openai"
}

resource "azurerm_cognitive_account" "this" {
  #checkov:skip=CKV_AZURE_134:No VNet in this design; callers authenticate with Entra ID and local keys are disabled
  #checkov:skip=CKV2_AZURE_22:Customer-managed keys need Key Vault, listed under production next steps
  name                  = var.account_name
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = local.is_openai ? "OpenAI" : "TextAnalytics"
  sku_name              = local.is_openai ? var.openai_sku_name : var.language_sku_name
  custom_subdomain_name = var.account_name
  local_auth_enabled    = false
  tags                  = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_cognitive_deployment" "chat" {
  count = local.is_openai ? 1 : 0

  name                 = var.openai_deployment_name
  cognitive_account_id = azurerm_cognitive_account.this.id

  model {
    format  = "OpenAI"
    name    = var.openai_model_name
    version = var.openai_model_version
  }

  sku {
    name     = var.openai_deployment_sku
    capacity = var.openai_capacity
  }
}
