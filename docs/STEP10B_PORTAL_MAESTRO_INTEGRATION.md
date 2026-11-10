# Step 10B — Portal-triggered Maestro investigation

Status: **implemented, bound to a live HTTP Webhook connection, and deployed/activated in UiPath; Render configuration and the first portal-started live run remain pending**.

The existing Manual Trigger, Autonomous Agent, Transfer Operations Quick Form, review APIs, and deterministic financial rules are unchanged. The authored Flow source adds `PortalWebhook` as a second entry point into the same first `ValidateInput` step. It does not copy the investigation or reconciliation graph.

## Security and architecture

Public judges can continue to browse `/portal` and `/api/demo/transfers` without credentials. Starting a workflow is separate and fail-closed:

1. `POST /api/portal/session` validates `PORTAL_OPERATOR_ACCESS_KEY` and issues a short-lived, signed, HttpOnly, SameSite=Strict cookie plus a CSRF token.
2. `POST /api/portal/investigations` requires that cookie, CSRF token, and an `Idempotency-Key`.
3. The backend accepts only `TRF-1001` through `TRF-1005`, enforces per-operator/global limits, and persists a `PEX-...` tracking record in `/data/portal/transferiq.db`.
4. The backend makes exactly one bounded webhook POST. It does not automatically retry an uncertain delivery.
5. Webhook acceptance is recorded as `TRIGGERED`, never as workflow completion.
6. The existing review-run creation, reconciliation, plan preview, decision, and execution APIs advance the tracking record using the same `executionRequestId`/idempotency correlation.

The webhook receives only:

```json
{
  "transferId": "TRF-1002",
  "executionRequestId": "PEX-<32 lowercase hex characters>",
  "enableIXP": false
}
```

The Flow rejects extra/missing fields, a non-allowlisted transfer, a malformed execution ID, or any `enableIXP` value other than `false`. It parses `request_body`; it never reads, logs, or returns `request_headers`, which can contain the authentication value.

## Render environment variables

Keep real values only in Render environment settings. Do not use `VITE_*` names.

```text
PORTAL_INVESTIGATION_ENABLED=0
PORTAL_OPERATOR_ID=demo-operator
PORTAL_OPERATOR_ACCESS_KEY=<at least 16 random characters>
SESSION_SECRET=<at least 32 random characters>
PORTAL_SESSION_TTL_MINUTES=60
PORTAL_USER_MAX_ACTIVE=1
PORTAL_GLOBAL_MAX_ACTIVE=3
PORTAL_STARTS_PER_MINUTE=2
PORTAL_WORKFLOW_TIMEOUT_MINUTES=60
UIPATH_WEBHOOK_URL=<deployed UiPath HTTP Webhook URL>
UIPATH_WEBHOOK_AUTH_HEADER_NAME=X-TransferIQ-Webhook-Key
UIPATH_WEBHOOK_AUTH_HEADER_VALUE=<at least 16 random characters>
UIPATH_WEBHOOK_TIMEOUT_SECONDS=15
```

Leave `PORTAL_INVESTIGATION_ENABLED=0` until the issued UiPath webhook URL and matching authentication value have been added to Render and one bounded live test is ready. Production startup refuses incomplete settings when the flag is `1`.

## UiPath connection and Flow deployment

UiPath's HTTP Webhook connector supports header authentication. A missing or incorrect header returns 401 and does not start a run. The caller receives a 200 acceptance containing `webhookEventId`; it does not receive the Flow result.

1. In Integration Service, create an **HTTP Webhook** connection using header authentication. Use the same header name/value that will be stored in Render. Do not paste either into the Flow source.
2. Confirm the connection and folder:

   ```powershell
   uip is connections list --all-folders --output json
   ```

3. From `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation`, bind the authored `PortalWebhook` entry point:

   ```powershell
   uip maestro registry prepare uipath-http-webhook --action http-webhook --connection-id <CONNECTION_ID>
   ```

   The command must write real connection and folder values for the source labels `portalHttpWebhook` and `shared` into `.flow-sdk/bindings.json`. Do not invent GUIDs.

4. Preserve the working brownfield Flow. Decompile the unchanged canonical artifact to a separate baseline source, then compile baseline and edited source into separate directories and merge only the delta:

   ```powershell
   uip maestro flow decompile TransferIQ_Reconciliation.flow -o .flow-sdk/TransferIQ_Reconciliation.baseline.flow.ts --no-pipeline
   uip maestro flow compile .flow-sdk/TransferIQ_Reconciliation.baseline.flow.ts -o C:\tmp\transferiq-step10b\baseline\TransferIQ_Reconciliation.flow
   uip maestro flow compile .flow-sdk/TransferIQ_Reconciliation.flow.ts -o C:\tmp\transferiq-step10b\edited\TransferIQ_Reconciliation.flow
   uip maestro flow merge C:\tmp\transferiq-step10b\edited\TransferIQ_Reconciliation.flow --original TransferIQ_Reconciliation.flow -o C:\tmp\transferiq-step10b\candidate\TransferIQ_Reconciliation.flow --baseline C:\tmp\transferiq-step10b\baseline\TransferIQ_Reconciliation.flow
   uip maestro flow validate C:\tmp\transferiq-step10b\candidate\TransferIQ_Reconciliation.flow --output json
   ```

5. Only after `Data.Status` is `Valid` with real bindings, replace the canonical `.flow`, publish/deploy the Flow, and obtain the active URL:

   ```powershell
   uip is webhooks config uipath-http-webhook --connection-id <CONNECTION_ID> --element-instance-id <ELEMENT_INSTANCE_ID> --output json
   ```

   The URL is not active until the Flow and trigger are deployed. Store it only as `UIPATH_WEBHOOK_URL` in Render.

6. Deploy the backend/frontend commit to Render, set every environment value, and finally change `PORTAL_INVESTIGATION_ENABLED` to `1`.

Official references:

- https://docs.uipath.com/integration-service/automation-cloud/latest/user-guide/uipath-http-webhook-authentication
- https://docs.uipath.com/integration-service/automation-cloud/latest/user-guide/uipath-http-webhook
- https://docs.uipath.com/maestro-automate/automation-cloud/latest/user-guide/node-http-webhook
- https://docs.uipath.com/maestro/automation-cloud/latest/user-guide/triggers

## Acceptance test

Use one bounded run after configuration; do not repeatedly submit the same failing setup.

1. Verify `/health` and public `/portal` still work.
2. Open `TRF-1002` → **Investigation**.
3. Enter the configured demo operator access code. Confirm no webhook value appears in HTML, browser logs, network responses, or the compiled JavaScript bundle.
4. Click **Investigate with AI** once. Record the returned `PEX-...` ID.
5. Confirm the progress page reports `TRIGGERED`, then `INVESTIGATING`.
6. Confirm the validated agent result advances it to `AWAITING_HUMAN_REVIEW` and creates a real Quick Form task.
7. Complete the task in UiPath Action Center. Do not use portal approval buttons; none exist.
8. For approval, verify `COMPLETED / APPROVED / REVIEWED_WITH_OPEN_EXCEPTIONS`.
9. In a separate run, verify rejection produces `COMPLETED / REJECTED / REVIEW_REJECTED`.
10. Confirm SEC-104 remains `-20`, `positionsUnchanged=true`, `transferCompleted=false`, and `auditReference` resolves to the existing plan audit API.
11. Run TRF-1001 once and confirm the clean branch completes without a Quick Form.

Automatic polling is bounded to 60 attempts at five-second intervals. Reloading the progress route resumes a new bounded read window; it does not trigger another Flow.

## Error behavior

| Condition | Behavior |
|---|---|
| Feature or secrets not configured | Startup fails if enabled; otherwise session reports disabled and trigger POST returns 503 |
| Invalid operator code/session/CSRF | 401/403; no tracking record or webhook request |
| Duplicate browser submission | Same idempotency key returns the same record; a second active start is rejected |
| Per-user/global limit | 409/429; no webhook request |
| Webhook 401/403 | Tracking record becomes `FAILED` with a sanitized authentication summary |
| Webhook network/timeout | `FAILED`, explicitly marked uncertain/unavailable, and not retried |
| Agent/Flow never reaches backend | Active record becomes `TIMED_OUT` at its persisted deadline |
| Human task pending | `AWAITING_HUMAN_REVIEW`; the portal remains read-only for the decision |
| Human rejection | Existing decision/execute APIs produce `REVIEW_REJECTED`; positions remain unchanged |
| Incomplete final audit | Tracking becomes `FAILED` instead of reporting success |

## Verification performed on 2026-11-10

- Focused backend/Step 9/Maestro/migration regression: **151 passed**, one existing Starlette/httpx deprecation warning.
- Final complete backend suite: **467 passed**, one existing Starlette/httpx deprecation warning, 135.62 seconds.
- Frontend unit suite: **9 passed**.
- Frontend production build: **successful**.
- Untouched canonical Flow: product validation **Valid**.
- Live connection `TransferIQ Portal Inbound Webhook`: **Enabled** in `DemoFolder`; a direct connection ping returned **Success / Enabled / Connection is active**.
- Bound source compile: **77 nodes / 80 edges**, zero compile errors or warnings.
- Brownfield merged candidate and installed canonical artifact: product validation **Valid**.
- Solution resource refresh imported the HTTP Webhook connection. The one warning, `Connection ImplicitConnection not found in Resource Catalog`, belongs to the pre-existing managed backend HTTP activity and is unchanged.
- Solution package `TransferIQ-AI` version `1.0.0`: pack and publish **Success**.
- Deployment `TransferIQ-AI 1.0.0`: **DeploymentSucceeded / SuccessfulActivate** in `DemoFolder/TransferIQ-AI` (pipeline deployment `5e3290db-1428-4c04-6644-08df3e764b94`).
- Deployed Flow inventory contains `TransferIQ_Reconciliation` version `1.0.0`; UiPath reports that a webhook URL was issued. The URL and authentication value are intentionally not recorded in this document.
- Actual HTTP Webhook call: **not executed**.
- Actual portal-started Maestro run or Quick Form: **not executed**.

The connection/binding/deployment blocker is resolved. Remaining work is to copy the issued webhook URL and the same header value used by the connection into Render, keep the feature disabled until those values are saved, redeploy Render, enable the feature, and execute one bounded TRF-1002 portal test. Step 9's already verified Quick Form approval/rejection evidence is not relabelled as a Step 10B webhook test.
