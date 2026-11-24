output "app_id" {
  description = "Resource id of the Function App."
  value       = azurerm_function_app_flex_consumption.app.id
}

output "app_name" {
  description = "Name of the Function App."
  value       = azurerm_function_app_flex_consumption.app.name
}

output "default_hostname" {
  description = "Default host name of the Function App."
  value       = azurerm_function_app_flex_consumption.app.default_hostname
}

output "identity_principal_id" {
  description = "Object id of the app's user-assigned identity (for role assignments)."
  value       = azurerm_user_assigned_identity.app.principal_id
}

output "identity_client_id" {
  description = "Client id of the app's user-assigned identity."
  value       = azurerm_user_assigned_identity.app.client_id
}

output "storage_account_id" {
  description = "Resource id of the app's host/deployment storage account."
  value       = azurerm_storage_account.host.id
}
