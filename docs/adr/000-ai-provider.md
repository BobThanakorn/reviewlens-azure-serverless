# ADR 000: AI provider for classification

Status: Accepted (2026-11-25), based on real tests in `docs/feasibility.md`

## Context
The brief prefers Azure OpenAI but says it may be blocked or have zero quota on an Azure for Students subscription, and asks for a fallback to Azure AI Language.

## Decision
Use **Azure OpenAI, model `gpt-5-nano`**, in `southeastasia`, selected by `CLASSIFIER_PROVIDER=openai`. Settings: `GlobalStandard`, capacity 50, `reasoning_effort=minimal`, `max_completion_tokens=800`, API version `2025-04-01-preview`. Authentication is Entra ID through the Function App's managed identity (`Cognitive Services OpenAI User`); local keys are disabled.

Evidence: an account and a deployment were created and called successfully on this subscription; Thai reviews were classified into valid JSON with Thai summaries (a 3-review feasibility run only). With `minimal` effort a review costs about 600 to 900 input tokens and about 50 output tokens, in 1.5 to 3.3 seconds.

The `language` provider (Azure AI Language sentiment, keyword topic table, first 120 characters as summary) remains implemented and unit-tested behind the same `Classifier` interface. It is not deployed by default.

## Alternatives considered
- `gpt-4.1-nano`: accepts the old request parameters but is marked Legacy.
- `gpt-4o-mini`: marked Deprecating and has no quota entry in `southeastasia`.
- Azure AI Language: the free tier F0 is already used by another resource in the same region, so it would need the paid tier or another region; Thai support was not verified.

## Consequences
- The gpt-5 family is a reasoning family: it rejects `temperature` and `max_tokens`, and reasoning tokens count toward the output limit. Without `minimal` effort a review used 950 to 1,725 output tokens, so the setting is essential for cost and speed.
- Capacity must be right at creation; changing it on an existing deployment did not take effect (runbook incident 7).
- Model lifecycles change over time. Switching model is an app-setting and Terraform-variable change (runbook procedure "change model").
- Accuracy against star ratings is measured in `docs/evaluation.md`, not assumed here.
