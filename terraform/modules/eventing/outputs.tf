output "system_topic_id" {
  description = "Resource id of the Event Grid system topic."
  value       = azurerm_eventgrid_system_topic.storage.id
}

output "subscription_id" {
  description = "Resource id of the event subscription."
  value       = azurerm_eventgrid_system_topic_event_subscription.raw_to_queue.id
}
