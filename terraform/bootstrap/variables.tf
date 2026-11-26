variable "location" {
  description = "Azure region for every resource. Must be allowed by the subscription's Azure Policy (see docs/feasibility.md)."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository allowed to log in through OIDC, as <owner>/<repo>."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repo))
    error_message = "github_repo must look like owner/repo."
  }
}

variable "github_oidc_repo" {
  description = "Repository part of the GitHub OIDC subject when it differs from github_repo. New repositories present immutable ids, e.g. owner@<owner id>/repo@<repo id> (see docs/github-setup.md). Null uses github_repo."
  type        = string
  default     = null

  validation {
    condition     = var.github_oidc_repo == null || can(regex("^[A-Za-z0-9_.@-]+/[A-Za-z0-9_.@-]+$", var.github_oidc_repo))
    error_message = "github_oidc_repo must look like owner@id/repo@id."
  }
}

variable "state_resource_group_name" {
  description = "Resource group for the Terraform state account and the CI identities."
  type        = string
  default     = "rg-reviewlens-tfstate"
}

variable "app_resource_group_name" {
  description = "Resource group that envs/dev deploys into."
  type        = string
  default     = "rg-reviewlens-dev"
}

variable "name_prefix" {
  description = "Short prefix for resource names."
  type        = string
  default     = "rl"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    Project     = "reviewlens"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}
