variable "location" {
  description = "Azure region. Must be allowed by the subscription's Azure Policy and support Flex Consumption (docs/feasibility.md)."
  type        = string
}

variable "resource_group_name" {
  description = "Existing resource group created by terraform/bootstrap."
  type        = string
  default     = "rg-reviewlens-dev"
}

variable "name_prefix" {
  description = "Short prefix for names."
  type        = string
  default     = "rl"
}

variable "environment" {
  description = "Environment name used in names and tags."
  type        = string
  default     = "dev"
}

variable "alert_email" {
  description = "E-mail that receives alerts and budget notifications. Set in terraform.tfvars or TF_VAR_alert_email; never commit."
  type        = string
  sensitive   = true
}

variable "classifier_provider" {
  description = "AI provider: openai or language (decision in docs/adr/000-ai-provider.md)."
  type        = string
  default     = "language"

  validation {
    condition     = contains(["openai", "language"], var.classifier_provider)
    error_message = "classifier_provider must be openai or language."
  }
}

variable "data_admin_object_ids" {
  description = "Object ids that may read/write the data account with Entra auth (you, for bootstrap_data.py and evaluate.py, and the CI apply identity for the smoke test)."
  type        = list(string)
  default     = []
}

variable "python_version" {
  description = "Python runtime for both Function Apps."
  type        = string
  default     = "3.12"
}

variable "max_instances" {
  description = "Max scale-out instances per Function App."
  type        = number
  default     = 2
}

variable "enable_budget" {
  description = "Create the resource-group budget (only if docs/feasibility.md says budgets are supported)."
  type        = bool
  default     = false
}

variable "monthly_budget_usd" {
  description = "Monthly budget in USD."
  type        = number
  default     = 20
}

variable "budget_start_date" {
  description = "First day of a month, RFC3339."
  type        = string
  default     = "2026-12-01T00:00:00Z"
}

variable "openai_model_name" {
  description = "OpenAI model to deploy when classifier_provider = openai. PLACEHOLDER until Phase 0."
  type        = string
  default     = "gpt-4o-mini"
}

variable "openai_model_version" {
  description = "OpenAI model version. PLACEHOLDER until Phase 0."
  type        = string
  default     = "2024-07-18"
}

variable "openai_deployment_sku" {
  description = "OpenAI deployment SKU. PLACEHOLDER until Phase 0."
  type        = string
  default     = "GlobalStandard"
}

variable "openai_capacity" {
  description = "OpenAI deployment capacity (thousand tokens per minute)."
  type        = number
  default     = 10
}
