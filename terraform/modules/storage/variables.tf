variable "account_name" {
  description = "Globally unique storage account name (3-24 lowercase letters and digits)."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to create the account in."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "containers" {
  description = "Private blob containers to create."
  type        = list(string)
  default     = ["source", "raw", "processed", "state"]
}

variable "queues" {
  description = "Storage queues to create (the poison queue is created by the Functions runtime but is declared here so alerts and RBAC can refer to it)."
  type        = list(string)
  default     = ["enrich", "enrich-poison"]
}

variable "tags" {
  description = "Tags for every resource."
  type        = map(string)
}
