# Module `functions`

One Flex Consumption Function App with its own user-assigned identity, host storage account (shared keys disabled) and deployment container. Used twice: pipeline and API (ADR 006, 007).

## Resources

- `azurerm_user_assigned_identity.app`
- `azurerm_storage_account.host`
- `azurerm_storage_container.package`
- `azurerm_role_assignment.host_blob`
- `azurerm_role_assignment.host_queue`
- `azurerm_service_plan.app`
- `azurerm_function_app_flex_consumption.app`

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `app_name` | `string` | required | Function App name (globally unique), e.g. func-rl-dev-pipeline-abc123. |
| `storage_account_name` | `string` | required | Name of the app's own host/deployment storage account (3-24 lowercase letters and digits). |
| `resource_group_name` | `string` | required | Resource group for the app. |
| `location` | `string` | required | Azure region. Must support Flex Consumption (see docs/feasibility.md). |
| `python_version` | `string` | `"3.12"` | Python runtime version for Flex Consumption. |
| `max_instances` | `number` | `2` | Upper bound of scale-out instances (cost guard). |
| `instance_memory_mb` | `number` | `2048` | Memory per instance in MB (Flex Consumption allows 512, 2048 or 4096). |
| `application_insights_connection_string` | `string` | required | Workspace-based Application Insights connection string. (sensitive) |
| `data_queue_service_uri` | `string` | `""` | Queue service URI of the data account. When set, the app gets an identity-based DataStorage connection for its queue trigger. |
| `app_settings` | `map(string)` | `{}` | Extra app settings (names and non-secret values only; the app uses managed identity). |
| `tags` | `map(string)` | required | Tags for every resource. |

## Outputs

| Name | Description |
|---|---|
| `app_id` | Resource id of the Function App. |
| `app_name` | Name of the Function App. |
| `default_hostname` | Default host name of the Function App. |
| `identity_principal_id` | Object id of the app's user-assigned identity (for role assignments). |
| `identity_client_id` | Client id of the app's user-assigned identity. |
| `storage_account_id` | Resource id of the app's host/deployment storage account. |

Generated from the module's `.tf` files; regenerate after changing inputs or outputs.
