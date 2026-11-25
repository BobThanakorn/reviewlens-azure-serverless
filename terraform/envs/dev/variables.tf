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
  default     = "openai"

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
  description = "OpenAI model to deploy when classifier_provider = openai (tested in Phase 0, ADR 000)."
  type        = string
  default     = "gpt-5-nano"
}

variable "openai_model_version" {
  description = "OpenAI model version (tested in Phase 0)."
  type        = string
  default     = "2025-08-07"
}

variable "openai_deployment_sku" {
  description = "OpenAI deployment SKU. GlobalStandard has quota in southeastasia (docs/feasibility.md)."
  type        = string
  default     = "GlobalStandard"
}

variable "openai_capacity" {
  description = "Capacity in thousand tokens per minute. Set it right at creation: changing it later did not take effect at the gateway in Phase 0 (docs/runbook.md)."
  type        = number
  default     = 50
}

variable "openai_reasoning_effort" {
  description = "reasoning_effort sent to gpt-5 models. minimal cut output from ~1,700 to ~50 tokens per review in Phase 0."
  type        = string
  default     = "minimal"
}
