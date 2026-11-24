output "account_id" {
  description = "Resource id of the static website storage account."
  value       = azurerm_storage_account.web.id
}

output "account_name" {
  description = "Name of the static website storage account (upload target)."
  value       = azurerm_storage_account.web.name
}

output "web_container_id" {
  description = "ARM resource id of the $web container (role scope for uploads)."
  value       = "${azurerm_storage_account.web.id}/blobServices/default/containers/$web"
}

output "website_url" {
  description = "Public URL of the dashboard, without a trailing slash."
  value       = trimsuffix(azurerm_storage_account.web.primary_web_endpoint, "/")
}
