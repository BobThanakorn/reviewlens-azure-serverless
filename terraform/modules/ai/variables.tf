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
  description = "Model to deploy. PLACEHOLDER: confirm availability and quota in docs/feasibility.md."
  type        = string
  default     = "gpt-4o-mini"
}

variable "openai_model_version" {
  description = "Model version. PLACEHOLDER: confirm in docs/feasibility.md."
  type        = string
  default     = "2024-07-18"
}

variable "openai_deployment_sku" {
  description = "Deployment SKU, for example Standard or GlobalStandard. PLACEHOLDER: depends on region and quota."
  type        = string
  default     = "GlobalStandard"
}

variable "openai_capacity" {
  description = "Deployment capacity in thousands of tokens per minute. Keep small to cap cost."
  type        = number
  default     = 10
}

variable "tags" {
  description = "Tags for every resource."
  type        = map(string)
}
