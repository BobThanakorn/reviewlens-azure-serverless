terraform {
  required_version = ">= 1.10"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "5.15.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.9.1"
    }
    local = {
      source  = "hashicorp/local"
      version = "2.9.1"
    }
  }
}

# Subscription comes from ARM_SUBSCRIPTION_ID (never committed).
provider "azurerm" {
  features {}

  resource_provider_registrations = "none"
  storage_use_azuread             = true
}
