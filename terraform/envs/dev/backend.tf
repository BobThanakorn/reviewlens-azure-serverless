# Remote state in Azure Storage with Entra auth; the backend uses blob lease locking natively.
# Account and resource group are supplied at init time so no environment-specific value is
# committed:  terraform init -backend-config=backend.hcl   (copy backend.hcl.example)
terraform {
  backend "azurerm" {
    use_azuread_auth = true
    container_name   = "tfstate"
    key              = "dev.tfstate"
  }
}
