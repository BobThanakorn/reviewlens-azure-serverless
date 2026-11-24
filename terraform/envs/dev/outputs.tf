output "dashboard_url" {
  description = "Public URL of the static website dashboard."
  value       = module.web.website_url
}

output "api_base_url" {
  description = "Base URL of the read-only API."
  value       = local.api_base_url
}

output "pipeline_app_name" {
  description = "Name of func-pipeline (used by scripts/deploy_functions.py)."
  value       = module.func_pipeline.app_name
}

output "api_app_name" {
  description = "Name of func-api (used by scripts/deploy_functions.py)."
  value       = module.func_api.app_name
}

output "resource_group_name" {
  description = "Resource group of the environment."
  value       = local.rg
}

output "data_storage_account_name" {
  description = "Data lake storage account (bootstrap_data.py, evaluate.py, smoke_test.py)."
  value       = module.storage.name
}

output "data_blob_url" {
  description = "Blob endpoint of the data account."
  value       = module.storage.blob_endpoint
}

output "data_queue_url" {
  description = "Queue endpoint of the data account."
  value       = module.storage.queue_endpoint
}

output "web_storage_account_name" {
  description = "Static website storage account (dashboard upload target)."
  value       = module.web.account_name
}

output "classifier_provider" {
  description = "Provider the pipeline was configured with."
  value       = var.classifier_provider
}
