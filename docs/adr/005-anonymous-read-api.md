# ADR 005: Anonymous, read-only API

Status: Accepted (trade-off documented)

## Context
The dashboard is a static page with no login. The data is a public, sampled review dataset and contains no personal information.

## Decision
`func-api` exposes four `GET` routes with anonymous auth. Protection comes from design instead of authentication:
- the API identity has only `Storage Blob Data Reader` on the `processed` container (no write, no AI, no queue);
- strict whitelist validation (`days` 1-30, `limit` 1-100, `sentiment` enum, unknown parameters rejected);
- CORS allows exactly one origin, the static website, with no wildcard;
- Flex Consumption `maximumInstanceCount = 2` bounds cost under abusive traffic;
- the admin backfill lives on `func-pipeline` behind a function key, never on the API.

## Consequences
- Anyone can read the aggregates and call the API directly (CORS only protects browsers). Acceptable for public data.
- A request flood could consume free credit. Mitigation here is the instance cap and the budget alert; real mitigation is below.
- **Production next step:** Entra ID authentication (App Service authentication) and Azure Front Door with WAF and rate limiting, plus private networking for storage.
