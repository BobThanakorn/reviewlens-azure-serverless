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
  }
}

# The subscription is read from ARM_SUBSCRIPTION_ID (never committed). Locally:
#   $env:ARM_SUBSCRIPTION_ID = az account show --query id -o tsv
provider "azurerm" {
  features {}

  # Resource providers are registered once by a human (subscription scope); the CI identities
  # only have rights inside the app resource group.
  resource_provider_registrations = "none"
  storage_use_azuread             = true
}
