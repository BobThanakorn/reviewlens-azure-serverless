variable "system_topic_name" {
  description = "Name of the Event Grid system topic."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group for the topic."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "storage_account_id" {
  description = "Resource id of the data storage account that raises BlobCreated events."
  type        = string
}

variable "queue_name" {
  description = "Name of the queue that receives the events."
  type        = string
  default     = "enrich"
}

variable "raw_container_name" {
  description = "Container whose new .jsonl blobs trigger enrichment."
  type        = string
  default     = "raw"
}

variable "tags" {
  description = "Tags for every resource."
  type        = map(string)
}
