output "id" {
  description = "Resource id of the data storage account."
  value       = azurerm_storage_account.data.id
}

output "name" {
  description = "Name of the data storage account."
  value       = azurerm_storage_account.data.name
}

output "blob_endpoint" {
  description = "Blob service endpoint (https://<account>.blob.core.windows.net/)."
  value       = azurerm_storage_account.data.primary_blob_endpoint
}

output "queue_endpoint" {
  description = "Queue service endpoint (https://<account>.queue.core.windows.net/)."
  value       = azurerm_storage_account.data.primary_queue_endpoint
}

output "container_ids" {
  description = "Map of container name to ARM resource id, used as exact role-assignment scopes."
  value       = { for name, c in azurerm_storage_container.this : name => "${azurerm_storage_account.data.id}/blobServices/default/containers/${c.name}" }
}

output "queue_ids" {
  description = "Map of queue name to ARM resource id, used as exact role-assignment scopes."
  value       = { for name, q in azurerm_storage_queue.this : name => "${azurerm_storage_account.data.id}/queueServices/default/queues/${q.name}" }
}
