# ADR 007: User-assigned managed identities for the Function Apps

Status: Accepted

## Context
Flex Consumption reads its deployment package from a storage container, and the host needs blob and queue access to start. With identity-based storage the role assignments must exist before the app can start. A system-assigned identity only exists after the app is created, which creates a chicken-and-egg problem.

## Decision
Each app gets a **user-assigned** identity created and authorised in the same Terraform module before the app itself. App settings set `AZURE_CLIENT_ID` so `DefaultAzureCredential` picks that identity, and the identity-based connections (`AzureWebJobsStorage__*`, `DataStorage__*`) carry `__credential=managedidentity` and `__clientId`.

## Consequences
- No connection strings or keys in app settings anywhere; shared-key access is disabled on every storage account.
- Forgetting `AZURE_CLIENT_ID` is a silent failure mode (the SDK cannot choose among identities), so the module always sets it.
- Role assignments can be declared before the app exists and `depends_on` orders them correctly.
