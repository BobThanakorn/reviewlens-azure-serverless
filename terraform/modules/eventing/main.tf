terraform {
  required_version = ">= 1.10"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.0, < 6.0"
    }
  }
}

# BlobCreated events of the data account are delivered to the `enrich` queue. Delivery uses the
# system topic's managed identity, so no queue key or SAS is stored anywhere.
resource "azurerm_eventgrid_system_topic" "storage" {
  name                = var.system_topic_name
  resource_group_name = var.resource_group_name
  location            = var.location
  source_resource_id  = var.storage_account_id
  topic_type          = "Microsoft.Storage.StorageAccounts"
  tags                = var.tags

  identity {
    type = "SystemAssigned"
  }
}

# Storage Queue Data Message Sender, scoped to the single queue it writes to.
resource "azurerm_role_assignment" "topic_sends_to_queue" {
  scope                = var.queue_id
  role_definition_name = "Storage Queue Data Message Sender"
  principal_id         = azurerm_eventgrid_system_topic.storage.identity[0].principal_id
}

resource "azurerm_eventgrid_system_topic_event_subscription" "raw_to_queue" {
  name                = "raw-jsonl-to-enrich-queue"
  resource_group_name = var.resource_group_name
  system_topic        = azurerm_eventgrid_system_topic.storage.name

  event_delivery_schema = "EventGridSchema"
  included_event_types  = ["Microsoft.Storage.BlobCreated"]

  # Blob event subjects look like /blobServices/default/containers/<container>/blobs/<path>,
  # so the filter must include the container path, not just "raw/".
  subject_filter {
    subject_begins_with = "/blobServices/default/containers/${var.raw_container_name}/"
    subject_ends_with   = ".jsonl"
  }

  delivery_identity {
    type = "SystemAssigned"
  }

  storage_queue_endpoint {
    storage_account_id = var.storage_account_id
    queue_name         = var.queue_name
  }

  retry_policy {
    max_delivery_attempts = 10
    event_time_to_live    = 1440
  }

  depends_on = [azurerm_role_assignment.topic_sends_to_queue]
}
