# Module `monitoring`

Log Analytics, Application Insights, an e-mail action group, three log alerts (function failures, poison queue, slow enrich), a workbook and an optional resource-group budget.

## Resources

- `azurerm_log_analytics_workspace.this`
- `azurerm_application_insights.this`
- `azurerm_monitor_action_group.email`
- `azurerm_monitor_scheduled_query_rules_alert_v2.poison`
- `azurerm_monitor_scheduled_query_rules_alert_v2.failures`
- `azurerm_monitor_scheduled_query_rules_alert_v2.enrich_duration`
- `random_uuid.workbook`
- `azurerm_application_insights_workbook.overview`
- `azurerm_consumption_budget_resource_group.this`

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `name` | `string` | required | Name stem for monitoring resources, e.g. rl-dev. |
| `resource_group_name` | `string` | required | Resource group for the monitoring resources. |
| `resource_group_id` | `string` | required | Resource id of the resource group (budget scope). |
| `location` | `string` | required | Azure region. |
| `alert_email` | `string` | required | E-mail address that receives alerts and budget notifications. Never commit it. (sensitive) |
| `data_storage_account_id` | `string` | required | Resource id of the data storage account (queue length tile). |
| `retention_days` | `number` | `30` | Log Analytics retention in days. |
| `daily_quota_gb` | `number` | `0.5` | Daily ingestion cap of the Log Analytics workspace (cost guard). |
| `function_timeout_minutes` | `number` | `30` | functionTimeout of the enrich function in minutes (host.json); the alert fires at 80% of it. |
| `enable_budget` | `bool` | `false` | Create the resource-group budget. Keep false until docs/feasibility.md confirms budgets work on this subscription. |
| `monthly_budget_usd` | `number` | `20` | Monthly budget in USD for the resource group. |
| `budget_start_date` | `string` | `"2026-12-01T00:00:00Z"` | First day of a month, RFC3339 (budgets must start on the first of a month). |
| `tags` | `map(string)` | required | Tags for every resource. |

## Outputs

| Name | Description |
|---|---|
| `application_insights_id` | Resource id of Application Insights. |
| `application_insights_connection_string` | Connection string for the Function Apps. |
| `workspace_id` | Resource id of the Log Analytics workspace. |
| `action_group_id` | Resource id of the e-mail action group. |

Generated from the module's `.tf` files; regenerate after changing inputs or outputs.
