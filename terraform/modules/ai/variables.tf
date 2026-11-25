variable "provider_kind" {
  description = "Which AI provider to create: openai or language. Decided in Phase 0 (docs/adr/000-ai-provider.md)."
  type        = string

  validation {
    condition     = contains(["openai", "language"], var.provider_kind)
    error_message = "provider_kind must be openai or language."
  }
}

variable "account_name" {
  description = "Account name, also used as the custom sub-domain (globally unique, 2-64 chars)."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the account."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "language_sku_name" {
  description = "SKU of the Language account. F0 is the free tier."
  type        = string
  default     = "F0"
}

variable "openai_sku_name" {
  description = "SKU of the OpenAI account."
  type        = string
  default     = "S0"
}

variable "openai_deployment_name" {
  description = "Name of the chat model deployment (used as the model name in API calls)."
  type        = string
  default     = "chat"
}

variable "openai_model_name" {
  description = "Model to deploy. Tested in Phase 0 (docs/feasibility.md)."
  type        = string
  default     = "gpt-5-nano"
}

variable "openai_model_version" {
  description = "Model version. Tested in Phase 0."
  type        = string
  default     = "2025-08-07"
}

variable "openai_deployment_sku" {
  description = "Deployment SKU, for example Standard or GlobalStandard. GlobalStandard has quota in southeastasia."
  type        = string
  default     = "GlobalStandard"
}

variable "openai_capacity" {
  description = "Deployment capacity in thousands of tokens per minute. Keep small to cap cost."
  type        = number
  default     = 50
}

variable "tags" {
  description = "Tags for every resource."
  type        = map(string)
}
