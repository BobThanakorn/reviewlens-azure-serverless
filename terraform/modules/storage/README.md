# Module `storage`

Data lake account (`source`, `raw`, `processed`, `state` containers) and the `enrich` / `enrich-poison` queues. Shared-key access disabled, soft delete on.

## Resources

- `azurerm_storage_account.data`
- `azurerm_storage_container.this`
- `azurerm_storage_queue.this`

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `account_name` | `string` | required | Globally unique storage account name (3-24 lowercase letters and digits). |
| `resource_group_name` | `string` | required | Resource group to create the account in. |
| `location` | `string` | required | Azure region. |
| `containers` | `list(string)` | `["source", "raw", "processed", "state"]` | Private blob containers to create. |
| `queues` | `list(string)` | `["enrich", "enrich-poison"]` | Storage queues to create (the poison queue is created by the Functions runtime but is declared here so alerts and RBAC can refer to it). |
| `tags` | `map(string)` | required | Tags for every resource. |

## Outputs

| Name | Description |
|---|---|
| `id` | Resource id of the data storage account. |
| `name` | Name of the data storage account. |
| `blob_endpoint` | Blob service endpoint (https://<account>.blob.core.windows.net/). |
| `queue_endpoint` | Queue service endpoint (https://<account>.queue.core.windows.net/). |
| `container_ids` | Map of container name to ARM resource id, used as exact role-assignment scopes. |
| `queue_ids` | Map of queue name to ARM resource id, used as exact role-assignment scopes. |

Generated from the module's `.tf` files; regenerate after changing inputs or outputs.
