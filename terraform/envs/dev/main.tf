data "azurerm_resource_group" "app" {
  name = var.resource_group_name
}

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

locals {
  name   = "${var.name_prefix}-${var.environment}"
  stem   = "${var.name_prefix}${var.environment}" # no dashes: storage account names
  suffix = random_string.suffix.result
  rg     = data.azurerm_resource_group.app.name
  region = var.location

  tags = {
    Project     = "reviewlens"
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  use_openai = var.classifier_provider == "openai"

  # Hosts are known up front, so the API URL can go into web/config.js while the API app only
  # needs the website origin (no dependency cycle between the two).
  api_base_url = "https://${module.func_api.default_hostname}/api"
}

# ------------------------------------------------------------------ data lake

module "storage" {
  source = "../../modules/storage"

  account_name        = "st${local.stem}data${local.suffix}"
  resource_group_name = local.rg
  location            = local.region
  tags                = local.tags
}

# ------------------------------------------------------------------ AI provider

module "ai" {
  source = "../../modules/ai"

  provider_kind         = var.classifier_provider
  account_name          = "ai-${local.name}-${local.suffix}"
  resource_group_name   = local.rg
  location              = local.region
  openai_model_name     = var.openai_model_name
  openai_model_version  = var.openai_model_version
  openai_deployment_sku = var.openai_deployment_sku
  openai_capacity       = var.openai_capacity
  tags                  = local.tags
}

# ------------------------------------------------------------------ monitoring

module "monitoring" {
  source = "../../modules/monitoring"

  name                     = local.name
  resource_group_name      = local.rg
  resource_group_id        = data.azurerm_resource_group.app.id
  location                 = local.region
  alert_email              = var.alert_email
  data_storage_account_id  = module.storage.id
  function_timeout_minutes = 30 # keep equal to functionTimeout in src/pipeline/host.json
  enable_budget            = var.enable_budget
  monthly_budget_usd       = var.monthly_budget_usd
  budget_start_date        = var.budget_start_date
  tags                     = local.tags
}

# ------------------------------------------------------------------ function apps

module "func_pipeline" {
  source = "../../modules/functions"

  app_name                               = "func-${local.name}-pipeline-${local.suffix}"
  storage_account_name                   = "st${local.stem}pipe${local.suffix}"
  resource_group_name                    = local.rg
  location                               = local.region
  python_version                         = var.python_version
  max_instances                          = var.max_instances
  application_insights_connection_string = module.monitoring.application_insights_connection_string
  data_queue_service_uri                 = module.storage.queue_endpoint
  tags                                   = local.tags

  app_settings = merge(
    {
      DATA_BLOB_URL       = module.storage.blob_endpoint
      CLASSIFIER_PROVIDER = var.classifier_provider
    },
    local.use_openai ? {
      OPENAI_ENDPOINT         = module.ai.endpoint
      OPENAI_DEPLOYMENT       = module.ai.deployment_name
      OPENAI_REASONING_EFFORT = var.openai_reasoning_effort
      } : {
      LANGUAGE_ENDPOINT = module.ai.endpoint
    },
  )
}

module "func_api" {
  source = "../../modules/functions"

  app_name                               = "func-${local.name}-api-${local.suffix}"
  storage_account_name                   = "st${local.stem}api${local.suffix}"
  resource_group_name                    = local.rg
  location                               = local.region
  python_version                         = var.python_version
  max_instances                          = var.max_instances
  application_insights_connection_string = module.monitoring.application_insights_connection_string
  tags                                   = local.tags

  app_settings = {
    DATA_BLOB_URL = module.storage.blob_endpoint
    WEB_ORIGIN    = module.web.website_url
  }
}

# ------------------------------------------------------------------ eventing

module "eventing" {
  source = "../../modules/eventing"

  system_topic_name   = "evgt-${local.name}-data"
  resource_group_name = local.rg
  location            = local.region
  storage_account_id  = module.storage.id
  queue_id            = module.storage.queue_ids["enrich"]
  tags                = local.tags
}

# ------------------------------------------------------------------ dashboard

module "web" {
  source = "../../modules/web"

  account_name        = "st${local.stem}web${local.suffix}"
  resource_group_name = local.rg
  location            = local.region
  api_base_url        = local.api_base_url
  config_js_path      = "${path.root}/../../../web/config.js"
  tags                = local.tags
}

# ------------------------------------------------------------------ RBAC (exact scopes)

# pipeline: read/write the data lake, use the queue, call the AI account.
resource "azurerm_role_assignment" "pipeline_blob" {
  scope                = module.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.func_pipeline.identity_principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "pipeline_queue" {
  scope                = module.storage.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = module.func_pipeline.identity_principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "pipeline_ai" {
  scope                = module.ai.account_id
  role_definition_name = module.ai.role_name
  principal_id         = module.func_pipeline.identity_principal_id
  principal_type       = "ServicePrincipal"
}

# api: read-only, and only the processed container. No write and no AI role by design.
resource "azurerm_role_assignment" "api_processed_reader" {
  scope                = module.storage.container_ids["processed"]
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = module.func_api.identity_principal_id
  principal_type       = "ServicePrincipal"
}

# Humans / CI that run bootstrap_data.py, evaluate.py and smoke_test.py with Entra auth.
resource "azurerm_role_assignment" "admin_blob" {
  for_each = toset(var.data_admin_object_ids)

  scope                = module.storage.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}

resource "azurerm_role_assignment" "admin_queue" {
  for_each = toset(var.data_admin_object_ids)

  scope                = module.storage.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = each.value
}

# The CI apply identity uploads the dashboard; the deploying user may need the same locally.
resource "azurerm_role_assignment" "admin_web" {
  for_each = toset(var.data_admin_object_ids)

  scope                = module.web.account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = each.value
}
