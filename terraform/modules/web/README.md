# Module `web`

Static website account for the dashboard and a Terraform-rendered `web/config.js` that points the page at the API.

## Resources

- `azurerm_storage_account.web`
- `azurerm_storage_account_static_website.web`
- `local_file.config_js`

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `account_name` | `string` | required | Globally unique name of the static website storage account. |
| `resource_group_name` | `string` | required | Resource group for the account. |
| `location` | `string` | required | Azure region. |
| `api_base_url` | `string` | required | Base URL of func-api, written into web/config.js (for example https://<host>/api). |
| `config_js_path` | `string` | required | Where to write the generated config.js (relative to the Terraform working directory). |
| `tags` | `map(string)` | required | Tags for every resource. |

## Outputs

| Name | Description |
|---|---|
| `account_id` | Resource id of the static website storage account. |
| `account_name` | Name of the static website storage account (upload target). |
| `web_container_id` | ARM resource id of the $web container (role scope for uploads). |
| `website_url` | Public URL of the dashboard, without a trailing slash. |

Generated from the module's `.tf` files; regenerate after changing inputs or outputs.
