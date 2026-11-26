# Module `eventing`

Event Grid system topic on the data account. `BlobCreated` events for `raw/*.jsonl` go to the `enrich` queue, delivered with the topic's managed identity. See ADR 009 for the account-scoped role.

## Resources

- `azurerm_eventgrid_system_topic.storage`
- `azurerm_role_assignment.topic_sends_to_queue`
- `azurerm_eventgrid_system_topic_event_subscription.raw_to_queue`

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `system_topic_name` | `string` | required | Name of the Event Grid system topic. |
| `resource_group_name` | `string` | required | Resource group for the topic. |
| `location` | `string` | required | Azure region. |
| `storage_account_id` | `string` | required | Resource id of the data storage account that raises BlobCreated events. |
| `queue_name` | `string` | `"enrich"` | Name of the queue that receives the events. |
| `raw_container_name` | `string` | `"raw"` | Container whose new .jsonl blobs trigger enrichment. |
| `tags` | `map(string)` | required | Tags for every resource. |

## Outputs

| Name | Description |
|---|---|
| `system_topic_id` | Resource id of the Event Grid system topic. |
| `subscription_id` | Resource id of the event subscription. |

Generated from the module's `.tf` files; regenerate after changing inputs or outputs.
