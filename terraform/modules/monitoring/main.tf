terraform {
  required_version = ">= 1.10"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 5.0, < 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0, < 4.0"
    }
  }
}

locals {
  timeout_alert_ms = floor(var.function_timeout_minutes * 60 * 1000 * 0.8)
}

# ------------------------------------------------------------------ workspace + App Insights

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_days
  daily_quota_gb      = var.daily_quota_gb
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = "appi-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  tags                = var.tags
}

# ------------------------------------------------------------------ alerting

resource "azurerm_monitor_action_group" "email" {
  name                = "ag-${var.name}"
  resource_group_name = var.resource_group_name
  short_name          = "reviewlens"
  tags                = var.tags

  email_receiver {
    name                    = "owner"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "poison" {
  name                = "alert-${var.name}-poison-queue"
  display_name        = "ReviewLens: message moved to the poison queue"
  description         = "The enrich function gave up on a queue message after maxDequeueCount attempts."
  resource_group_name = var.resource_group_name
  location            = var.location
  scopes              = [azurerm_application_insights.this.id]
  severity            = 1

  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      traces
      | where message has "MaxDequeueCount" and message has "poison"
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.email.id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "failures" {
  name                = "alert-${var.name}-function-failures"
  display_name        = "ReviewLens: function failures in the last 5 minutes"
  description         = "At least one failed request or exception in either Function App."
  resource_group_name = var.resource_group_name
  location            = var.location
  scopes              = [azurerm_application_insights.this.id]
  severity            = 2

  evaluation_frequency = "PT5M"
  window_duration      = "PT5M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      union
        (exceptions | project timestamp),
        (requests | where success == false | project timestamp)
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.email.id]
  }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "enrich_duration" {
  name                = "alert-${var.name}-enrich-duration"
  display_name        = "ReviewLens: enrich is close to its timeout"
  description         = "An enrich run took more than 80% of functionTimeout (${var.function_timeout_minutes} min)."
  resource_group_name = var.resource_group_name
  location            = var.location
  scopes              = [azurerm_application_insights.this.id]
  severity            = 2

  evaluation_frequency = "PT15M"
  window_duration      = "PT15M"
  tags                 = var.tags

  criteria {
    query                   = <<-KQL
      requests
      | where operation_Name == "enrich" and duration > ${local.timeout_alert_ms}
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.email.id]
  }
}

# ------------------------------------------------------------------ workbook

resource "random_uuid" "workbook" {}

resource "azurerm_application_insights_workbook" "overview" {
  name                = random_uuid.workbook.result
  display_name        = "ReviewLens overview"
  resource_group_name = var.resource_group_name
  location            = var.location
  source_id           = lower(azurerm_application_insights.this.id)
  tags                = var.tags

  data_json = jsonencode({
    version = "Notebook/1.0"
    items = [
      {
        type    = 1
        content = { json = "## ReviewLens pipeline health\nStructured log events emitted by the Function Apps." }
        name    = "title"
      },
      {
        type = 3
        content = {
          version                 = "KqlItem/1.0"
          title                   = "Chunks ingested per day"
          queryType               = 0
          resourceType            = "microsoft.insights/components"
          crossComponentResources = [azurerm_application_insights.this.id]
          visualization           = "barchart"
          query                   = <<-KQL
            traces
            | where message has "\"event\": \"ingest_chunk\""
            | summarize chunks = count() by bin(timestamp, 1d)
          KQL
        }
        name = "ingested"
      },
      {
        type = 3
        content = {
          version                 = "KqlItem/1.0"
          title                   = "Enrich failures (review level and function level)"
          queryType               = 0
          resourceType            = "microsoft.insights/components"
          crossComponentResources = [azurerm_application_insights.this.id]
          visualization           = "timechart"
          query                   = <<-KQL
            union
              (traces | where message has "enrich_review_failed" | project timestamp, kind = "review"),
              (exceptions | project timestamp, kind = "exception")
            | summarize failures = count() by bin(timestamp, 1h), kind
          KQL
        }
        name = "failures"
      },
      {
        type = 3
        content = {
          version                 = "KqlItem/1.0"
          title                   = "Classifier latency per review (ms, average per chunk)"
          queryType               = 0
          resourceType            = "microsoft.insights/components"
          crossComponentResources = [azurerm_application_insights.this.id]
          visualization           = "timechart"
          query                   = <<-KQL
            traces
            | where message has "enrich_chunk_done"
            | extend d = parse_json(message)
            | project timestamp, avg_latency_ms = todouble(d.avg_latency_ms), tokens = toint(d.input_tokens) + toint(d.output_tokens)
          KQL
        }
        name = "latency"
      },
      {
        type = 10
        content = {
          version      = "MetricsItem/2.0"
          size         = 4
          title        = "Queue messages (enrich + poison, whole account)"
          queryType    = 2
          resourceType = "microsoft.storage/storageaccounts"
          resourceIds  = ["${var.data_storage_account_id}/queueServices/default"]
          timeContext  = { durationMs = 86400000 }
          metrics = [{
            namespace   = "microsoft.storage/storageaccounts/queueservices"
            metric      = "microsoft.storage/storageaccounts/queueservices-Capacity-QueueMessageCount"
            aggregation = 4
          }]
        }
        name = "queue-length"
      },
    ]
  })
}

# ------------------------------------------------------------------ budget (optional)

# Budgets may be unavailable on Azure for Students; enable only after docs/feasibility.md confirms.
resource "azurerm_consumption_budget_resource_group" "this" {
  count = var.enable_budget ? 1 : 0

  name              = "budget-${var.name}"
  resource_group_id = var.resource_group_id
  amount            = var.monthly_budget_usd
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 50
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = [var.alert_email]
  }
}
