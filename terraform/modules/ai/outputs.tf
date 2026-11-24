output "account_id" {
  description = "Resource id of the AI account (role-assignment scope)."
  value       = azurerm_cognitive_account.this.id
}

output "endpoint" {
  description = "Endpoint of the account (custom sub-domain, supports Entra auth)."
  value       = azurerm_cognitive_account.this.endpoint
}

output "deployment_name" {
  description = "Name of the chat deployment (empty for the language provider)."
  value       = try(azurerm_cognitive_deployment.chat[0].name, "")
}

output "role_name" {
  description = "Built-in role that lets the pipeline call this account."
  value       = local.is_openai ? "Cognitive Services OpenAI User" : "Cognitive Services User"
}
