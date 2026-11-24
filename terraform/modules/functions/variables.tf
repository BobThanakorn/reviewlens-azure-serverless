variable "app_name" {
  description = "Function App name (globally unique), e.g. func-rl-dev-pipeline-abc123."
  type        = string
}

variable "storage_account_name" {
  description = "Name of the app's own host/deployment storage account (3-24 lowercase letters and digits)."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the app."
  type        = string
}

variable "location" {
  description = "Azure region. Must support Flex Consumption (see docs/feasibility.md)."
  type        = string
}

variable "python_version" {
  description = "Python runtime version for Flex Consumption."
  type        = string
  default     = "3.12"
}

variable "max_instances" {
  description = "Upper bound of scale-out instances (cost guard)."
  type        = number
  default     = 2
}

variable "instance_memory_mb" {
  description = "Memory per instance in MB (Flex Consumption allows 512, 2048 or 4096)."
  type        = number
  default     = 2048
}

variable "application_insights_connection_string" {
  description = "Workspace-based Application Insights connection string."
  type        = string
  sensitive   = true
}

variable "data_queue_service_uri" {
  description = "Queue service URI of the data account. When set, the app gets an identity-based DataStorage connection for its queue trigger."
  type        = string
  default     = ""
}

variable "app_settings" {
  description = "Extra app settings (names and non-secret values only; the app uses managed identity)."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags for every resource."
  type        = map(string)
}
