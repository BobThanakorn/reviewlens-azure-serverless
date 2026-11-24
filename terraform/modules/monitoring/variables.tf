variable "name" {
  description = "Name stem for monitoring resources, e.g. rl-dev."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the monitoring resources."
  type        = string
}

variable "resource_group_id" {
  description = "Resource id of the resource group (budget scope)."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "alert_email" {
  description = "E-mail address that receives alerts and budget notifications. Never commit it."
  type        = string
  sensitive   = true
}

variable "data_storage_account_id" {
  description = "Resource id of the data storage account (queue length tile)."
  type        = string
}

variable "retention_days" {
  description = "Log Analytics retention in days."
  type        = number
  default     = 30
}

variable "daily_quota_gb" {
  description = "Daily ingestion cap of the Log Analytics workspace (cost guard)."
  type        = number
  default     = 0.5
}

variable "function_timeout_minutes" {
  description = "functionTimeout of the enrich function in minutes (host.json); the alert fires at 80% of it."
  type        = number
  default     = 30
}

variable "enable_budget" {
  description = "Create the resource-group budget. Keep false until docs/feasibility.md confirms budgets work on this subscription."
  type        = bool
  default     = false
}

variable "monthly_budget_usd" {
  description = "Monthly budget in USD for the resource group."
  type        = number
  default     = 20
}

variable "budget_start_date" {
  description = "First day of a month, RFC3339 (budgets must start on the first of a month)."
  type        = string
  default     = "2026-12-01T00:00:00Z"
}

variable "tags" {
  description = "Tags for every resource."
  type        = map(string)
}
