output "application_insights_id" {
  description = "Resource id of Application Insights."
  value       = azurerm_application_insights.this.id
}

output "application_insights_connection_string" {
  description = "Connection string for the Function Apps."
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
}

output "workspace_id" {
  description = "Resource id of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.this.id
}

output "action_group_id" {
  description = "Resource id of the e-mail action group."
  value       = azurerm_monitor_action_group.email.id
}
