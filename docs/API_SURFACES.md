# TransferIQ AI API surfaces

The OpenAPI document at /openapi.json is the route authority.

## Public service routes

| Method | Route | Purpose |
|---|---|---|
| GET | /health | Readiness and SQLite check |
| GET | /docs, /redoc, /openapi.json | API documentation and schema |
| GET | /portal, /portal/{path} | Compiled React SPA and route fallback |

## Precomputed public catalog

- GET /api/demo/transfers
- GET /api/demo/transfers/{transferId}

These routes return packaged fictional display fixtures. They do not create a run or query private application storage.

## Anonymous isolated demo-run reads and reconciliation

- POST /api/demo/runs
- GET /api/demo/runs/{runId}/transfer
- GET /api/demo/runs/{runId}/delivering/accounts/{accountId}/positions
- GET /api/demo/runs/{runId}/receiving/accounts/{accountId}/positions
- POST /api/demo/runs/{runId}/reconcile
- GET /api/demo/runs/{runId}/reconciliation
- GET /api/demo/runs/{runId}/exceptions
- GET /api/demo/runs/{runId}/documents
- GET /api/demo/runs/{runId}/corporate-actions
- GET /api/demo/runs/{runId}/documents/{documentId}/download
- GET /api/demo/runs/{runId}/documents/{documentId}/content
- GET /api/demo/runs/{runId}/investigation-references
- GET /api/demo/runs/{runId}/audit

Only TRF-1001 through TRF-1005 can create runs. State is isolated under DATA_DIR/competition and bounded by TTL, quotas, rate limits, and storage admission.

## Capability-scoped demo review

- POST /api/demo/runs/review
- POST /api/demo/runs/{runId}/resolution-plans/preview
- GET /api/demo/runs/{runId}/resolution-plans/{planId}
- POST /api/demo/runs/{runId}/resolution-plans/{planId}/decision
- POST /api/demo/runs/{runId}/resolution-plans/{planId}/execute
- GET /api/demo/runs/{runId}/resolution-plans/{planId}/verify
- GET /api/demo/runs/{runId}/resolution-plans/{planId}/audit

Review-run creation issues a scoped capability. Preview, decision, and execution require it. Public plan identifiers are not write authority. GETs expose sanitized synthetic state only.

## Controlled portal operations

- GET /api/portal/session
- POST /api/portal/session
- GET /api/portal/investigations?limit={1..50}&offset={0..}&transferId={optional allowlisted TRF ID}
- POST /api/portal/investigations
- GET /api/portal/investigations/{executionRequestId}

`POST /api/portal/session` is the credential-authenticated session bootstrap: it
issues a signed HttpOnly cookie and returns the session-bound CSRF token. It does
not require a pre-existing session or CSRF token. `POST
/api/portal/investigations` is the only cookie-authenticated portal mutation. It
requires the signed cookie, a non-empty matching `X-CSRF-Token`, and an
`Idempotency-Key`. Missing or incorrect CSRF is rejected with HTTP 403 before a
PEX row is created or the webhook is called.

History and detail GETs require the signed session cookie but intentionally do
not require CSRF because they are read-only. They return only sanitized
persisted PEX state. History is scoped to the authenticated operator, ordered
newest-first, optionally filtered by TRF-1001 through TRF-1005, and never starts
or retries a workflow.

The `/api/demo/runs...` review callbacks are independently authenticated
machine-to-machine operations. They use run isolation, idempotency, and scoped
review capabilities rather than the portal session cookie, so the portal CSRF
header does not apply to them.

## Private business and document APIs

All routes in this section require X-API-Key:

- GET /api/clients and /api/clients/{clientId}
- GET /api/firms
- GET /api/accounts/{accountId}
- POST and GET /api/transfers
- GET /api/transfers/{transferId}
- GET /api/transfers/{transferId}/assets
- GET /api/delivering/accounts/{accountId}/positions
- GET /api/receiving/accounts/{accountId}/positions
- GET /api/securities and /api/securities/{securityId}
- POST /api/transfers/{transferId}/reconcile
- GET /api/transfers/{transferId}/reconciliation
- GET /api/transfers/{transferId}/exceptions
- GET /api/reconciliation-runs/{runId}
- GET /api/corporate-actions
- GET /api/securities/{securityId}/corporate-actions
- GET /api/securities/{securityId}/identifier-mappings
- POST and GET /api/transfers/{transferId}/documents
- GET /api/documents/{documentId}
- GET /api/documents/{documentId}/download
- GET /api/transfers/{transferId}/documents/{documentId}/download

## Protected unavailable write boundary

The following X-API-Key-protected routes deliberately return 503 verified_review_not_configured:

- POST /api/resolution-plans/preview
- POST /api/resolution-plans/{planId}/decision
- POST /api/resolution-plans/{planId}/execute

They prevent synthetic demo reviewer references from authorizing private operations.

## Non-API UiPath callback

The portal backend calls the configured UiPath Integration Service HTTP Webhook URL. That URL and its authentication header are secrets and are not application routes, frontend configuration, or documentation examples.
