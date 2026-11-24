output "tenant_id" {
  description = "Value for the AZURE_TENANT_ID repository variable."
  value       = data.azurerm_client_config.current.tenant_id
}

output "subscription_id" {
  description = "Value for the AZURE_SUBSCRIPTION_ID repository variable."
  value       = data.azurerm_client_config.current.subscription_id
}

output "client_id_plan" {
  description = "Value for the AZURE_CLIENT_ID_PLAN repository variable."
  value       = azurerm_user_assigned_identity.plan.client_id
}

output "client_id_apply" {
  description = "Value for the AZURE_CLIENT_ID_APPLY repository variable."
  value       = azurerm_user_assigned_identity.apply.client_id
}

output "state_resource_group_name" {
  description = "Resource group holding the state account (use in backend.hcl)."
  value       = azurerm_resource_group.state.name
}

output "state_storage_account_name" {
  description = "State storage account (use in backend.hcl)."
  value       = azurerm_storage_account.state.name
}

output "state_container_name" {
  description = "State container (use in backend.hcl)."
  value       = azurerm_storage_container.state.name
}

output "app_resource_group_name" {
  description = "Resource group that envs/dev deploys into."
  value       = azurerm_resource_group.app.name
}

output "principal_id_apply" {
  description = "Object id of the apply identity. Add it to data_admin_object_ids so CI can read data for the smoke test."
  value       = azurerm_user_assigned_identity.apply.principal_id
}
