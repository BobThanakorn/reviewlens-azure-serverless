# Module `ai`

Azure OpenAI account (Entra auth only, local auth disabled) and one model deployment used by the enrich function. See ADR 000.

## Resources

- `azurerm_cognitive_account.this`
- `azurerm_cognitive_deployment.chat`

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `provider_kind` | `string` | required | Which AI provider to create: openai or language. Decided in Phase 0 (docs/adr/000-ai-provider.md). |
| `account_name` | `string` | required | Account name, also used as the custom sub-domain (globally unique, 2-64 chars). |
| `resource_group_name` | `string` | required | Resource group for the account. |
| `location` | `string` | required | Azure region. |
| `language_sku_name` | `string` | `"F0"` | SKU of the Language account. F0 is the free tier. |
| `openai_sku_name` | `string` | `"S0"` | SKU of the OpenAI account. |
| `openai_deployment_name` | `string` | `"chat"` | Name of the chat model deployment (used as the model name in API calls). |
| `openai_model_name` | `string` | `"gpt-5-nano"` | Model to deploy. Tested in Phase 0 (docs/feasibility.md). |
| `openai_model_version` | `string` | `"2025-08-07"` | Model version. Tested in Phase 0. |
| `openai_deployment_sku` | `string` | `"GlobalStandard"` | Deployment SKU, for example Standard or GlobalStandard. GlobalStandard has quota in southeastasia. |
| `openai_capacity` | `number` | `50` | Deployment capacity in thousands of tokens per minute. Keep small to cap cost. |
| `tags` | `map(string)` | required | Tags for every resource. |

## Outputs

| Name | Description |
|---|---|
| `account_id` | Resource id of the AI account (role-assignment scope). |
| `endpoint` | Endpoint of the account (custom sub-domain, supports Entra auth). |
| `deployment_name` | Name of the chat deployment (empty for the language provider). |
| `role_name` | Built-in role that lets the pipeline call this account. |

Generated from the module's `.tf` files; regenerate after changing inputs or outputs.
