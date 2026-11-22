# Credential-free synthetic demo

This guide describes the anonymous backend portion of TransferIQ AI. It does not mean the full UiPath tenant is zero-configuration.

## What requires no TransferIQ credential

- public portal browsing;
- health and OpenAPI reads;
- precomputed fictional catalog reads;
- allowlisted isolated demo-run creation and run-scoped reads;
- deterministic synthetic reconciliation;
- public resolution-plan, verification, and audit reads when run/plan IDs are known.

The complete route list and authorization boundaries are in [API_SURFACES.md](API_SURFACES.md).

## What still requires authorization

- private business and document APIs require X-API-Key;
- starting from the portal requires the signed operator session, CSRF token, and Idempotency-Key;
- review-plan writes require the capability issued to the Flow's review run;
- UiPath import/run requires a tenant with the appropriate entitlements;
- Quick Form completion requires an assignable Action Center user;
- the Portal Webhook uses a secret URL and authentication header.

## Current Flow behavior

The current 81-node/86-edge Flow is not the older reconciliation-only Flow:

- Manual Trigger and Portal Webhook share one graph;
- CLEAN cases finish without an agent or Quick Form;
- investigation cases use a real Autonomous Agent;
- a real PDF can be retrieved automatically and analyzed with Analyze Files;
- extracted fields are validated against independent API evidence;
- a real Approve/Reject Quick Form controls the demo disposition continuation;
- final verification and append-only audit are reread before completion.

IXP-in-Flow is unavailable in the Community tenant and is not invoked. Analyze Files is the supported implemented alternative.

## Anonymous run example

    $base = 'https://transferiq-api.onrender.com'
    $key = [guid]::NewGuid().ToString('N')
    $headers = @{'Idempotency-Key'=$key}
    $run = Invoke-RestMethod "$base/api/demo/runs" -Method Post -ContentType 'application/json' -Headers $headers -Body '{"transferId":"TRF-1002"}'
    $root = "$base/api/demo/runs/$($run.runId)"
    Invoke-RestMethod "$root/transfer"
    Invoke-RestMethod "$root/reconcile" -Method Post -ContentType 'application/json' -Body '{}'
    Invoke-RestMethod "$root/exceptions"
    Invoke-RestMethod "$root/investigation-references"

Idempotency-Key is a deduplication value, not authentication. Only TRF-1001 through TRF-1005 are accepted. Unknown transfers return 422, unknown runs return 404, and retained expired runs return 410. Quotas can return 429.

## Isolation and safety

Each run owns an isolated SQLite database and PDF directory under DATA_DIR/competition/runs. Anonymous routes do not use the private application session, accept arbitrary holdings, apply corrections, reset state, or settle a transfer.

Reconciliation and approved demo dispositions leave source and staging positions unchanged. For TRF-1002, SEC-104 remains unresolved at -20 even after the workflow completes.

## Full reproduction

Follow [JUDGE_REPRODUCTION_GUIDE.md](JUDGE_REPRODUCTION_GUIDE.md) for backend/frontend tests, pinned Flow source compilation, CLI 1.205.0 validation, tenant resource binding, reviewer assignment, trigger setup, and bounded live acceptance.

Historical Step 5 documents preserve the earlier reconciliation-only milestone and must not be used as the current Flow setup guide.
