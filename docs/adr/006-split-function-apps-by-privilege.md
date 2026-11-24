# ADR 006: Two Function Apps split by privilege

Status: Accepted

## Context
Ingest and enrich write data and call an AI service; the API only reads, and it is public and anonymous.

## Decision
`func-pipeline` (ingest timer, admin backfill, enrich queue trigger) and `func-api` (read-only routes) are separate apps with separate identities, plans and host storage accounts.

| | func-pipeline | func-api |
|---|---|---|
| Data account | Blob Data Contributor, Queue Data Contributor | Blob Data Reader on `processed` only |
| AI account | OpenAI User / Cognitive Services User | none |
| Exposure | timer, queue, key-protected HTTP | anonymous HTTP |

## Consequences
- An exploit of the public API cannot write data, drain the queue or spend AI quota; the blast radius is read access to public data.
- Cost is unchanged (both scale to zero); there is one extra deploy and one extra identity to manage.
- Each app still needs write access to its **own** host storage account (leases, deployment package). That account holds no business data.
