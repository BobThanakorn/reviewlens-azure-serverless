variable "account_name" {
  description = "Globally unique name of the static website storage account."
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

variable "api_base_url" {
  description = "Base URL of func-api, written into web/config.js (for example https://<host>/api)."
  type        = string
}

variable "config_js_path" {
  description = "Where to write the generated config.js (relative to the Terraform working directory)."
  type        = string
}

variable "tags" {
  description = "Tags for every resource."
  type        = map(string)
}
