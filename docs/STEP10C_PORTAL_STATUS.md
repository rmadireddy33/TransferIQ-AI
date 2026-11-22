# Step 10C — Persisted portal workflow status

Status: **implemented and deployed. Later 1.1.1 approval, rejection, and CLEAN
PEX lifecycles were live-verified and are recorded in
[Step 11](STEP11_AGENT_DOCUMENT_ANALYSIS.md) and
[live evidence](LIVE_EXECUTION_EVIDENCE.md).**

This increment improves how the existing portal reports the already deployed Maestro workflow. It does not change the HTTP Webhook request, the Flow artifact, Manual Trigger, Autonomous Agent, Quick Form, IXP configuration, reconciliation rules, or financial state.

## Root cause

The backend already had the correct terminal boundary: webhook HTTP 200 stored `TRIGGERED`, plan preview stored `AWAITING_HUMAN_REVIEW`, and only the Step 9 execute path called independent `verify()` and checked the audit ledger before storing `COMPLETED`.

The missing completion indication was a projection and presentation problem:

- the authorized tracking response omitted its persisted start timestamp and independent verification status;
- the audit reference was displayed as plain text instead of a usable read-only link;
- the React page used one generic status panel for every lifecycle state;
- its 60-request/five-second polling window stopped silently after about five minutes;
- a transient API error replaced the whole persisted view and offered no status-specific recovery.

## Backend status contract

`GET /api/portal/investigations/{executionRequestId}` remains cookie-authorized and reads the isolated SQLite portal registry. Its existing lifecycle values remain:

`PENDING`, `TRIGGERED`, `INVESTIGATING`, `AWAITING_HUMAN_REVIEW`, `COMPLETED`, `FAILED`, and `TIMED_OUT`.

The response now also includes:

- `startedAt`, `lastUpdated`, and `deadlineAt` from persisted UTC timestamps;
- `verificationStatus`, written from the existing Step 9 verification result;
- `auditUrl`, derived only when a correlated run, plan, and audit reference exist.

`GET /api/portal/investigations?limit=10&offset=0` provides paginated, read-only history over the same registry. An optional allowlisted `transferId` query filters the same operator-scoped result for an individual transfer page. The route requires the signed operator cookie, orders rows by persisted start time newest-first, and returns `items`, `total`, `limit`, and `offset`. It never dispatches a webhook, creates a run, changes financial data, or returns operator IDs, idempotency hashes, webhook event IDs, credentials, or capabilities.

Portal registry schema v2 adds only nullable `verification_status`. Startup migrates schema v1 with `ALTER TABLE`, preserves every PEX row, and rejects unsupported schemas instead of resetting them.

The 2026-11-22 presentation cleanup advances the isolated portal registry to schema v3 by adding only nullable `document_evidence_status`. Startup migrates either v1 or v2 in place and preserves every PEX row. The resolution-plan preview copies the existing `documentEvidenceStatus` into this sanitized projection; it does not store document bytes, capabilities, signed URLs, or credentials.

The active transfer Investigation tab and the dedicated PEX page now use that persisted value to distinguish `AGENT_ANALYZE_FILES`, `API_ONLY`, and document evidence unavailable. The previous hardcoded legacy IXP badge and unused duplicate progress component were removed. The active timeline now shows six backend-derived stages: investigation started, Maestro triggered, AI investigation in progress, awaiting human review, human decision recorded, and verified final outcome. CLEAN runs explicitly mark the two human stages as not required.

Completion semantics are unchanged and explicit:

- webhook acceptance is `TRIGGERED`, never completion;
- plan preview is `AWAITING_HUMAN_REVIEW` and normally `NOT_VERIFIED`;
- approval and rejection become `COMPLETED` only after the persisted plan, final decision, independent verification, and required audit events agree;
- `REVIEWED_WITH_OPEN_EXCEPTIONS` means the workflow completed, not that the brokerage transfer completed;
- `REVIEW_REJECTED` is presented as rejection, not generic success;
- the clean path is `CLEAN / NOT_REQUIRED` and has no fabricated plan audit URL;
- only the persisted server deadline can mark `TIMED_OUT`. A browser that stops polling cannot do so.

## Portal experience

The navigation includes `/portal/investigations`, an authorized Investigation History view over existing PEX rows. Each transfer page also includes an Investigation history tab backed by the same route with its `transferId` filter. Selecting a PEX opens `/portal/investigations/PEX-...`; its back navigation resolves to the correlated TRF transfer. Reloading any of these routes performs authorized reads and never starts another webhook execution.

The view now shows:

- transfer and execution request IDs;
- current workflow stage and status;
- started and last-updated timestamps;
- human-review status, final workflow outcome, and verification status;
- positions-unchanged and brokerage-transfer-completed results;
- a six-stage timeline without an invented percentage;
- final investigation summary, evidence references, and unresolved exceptions;
- sanitized failures and timeout information;
- `View Audit Report` and `View Transfer Details` actions when applicable.

Active records poll at five-second intervals for at most 60 requests. Terminal records stop immediately. When the active window is exhausted, the UI states that only client polling paused and offers `Refresh status`; that action starts a new bounded read window. API unavailability retains the last successful persisted view when one exists and also offers an explicit refresh.

No approval control exists in the portal. Reviewer action remains in UiPath Action Center.

The history table displays PEX ID, transfer ID, start time, workflow status, human-review status, final business outcome, verification status, and brokerage-transfer completion. Historical nullable fields render as `Not recorded`; the portal does not infer a verification result. `COMPLETED / REVIEWED_WITH_OPEN_EXCEPTIONS` is paired with `OPEN EXCEPTIONS`, keeping Maestro completion distinct from brokerage-transfer completion. Pagination uses bounded `limit`/`offset` reads and the empty state does not fabricate sample history.

## Files changed

- `backend/services/portal_investigations.py` — data-preserving registry v2 migration and richer sanitized projection.
- `backend/api/resolution.py` — copies the existing independent verification result into the portal projection at preview/final execution.
- `frontend/src/api.ts` — validates the expanded authorized tracking response.
- `frontend/src/App.tsx` — terminal-aware progress view, timeline, bounded-polling pause, refresh, and final navigation.
- `frontend/src/index.css` — responsive timeline and result-state presentation.
- `tests/test_step10b_portal.py` and `frontend/src/App.test.tsx` — persistence, lifecycle, audit, reload, failure, timeout, and polling regression coverage.

The Investigation History increments additionally change `backend/api/portal.py`, `backend/services/portal_investigations.py`, `frontend/src/api.ts`, `frontend/src/App.tsx`, and `frontend/src/index.css`, with backend/frontend coverage for authentication, operator isolation, global and transfer filtering, preserved nullable historical fields, empty states, pagination, PEX navigation, and the return link. They do not change the registry schema or reset existing rows.

## Verification

The focused backend suite uses a webhook test double and explicit agent/human test values; it is not a UiPath execution:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_step10b_portal.py -q --tb=short
```

Observed: **9 passed**, one existing Starlette/httpx deprecation warning.

Frontend unit suite:

```powershell
Set-Location frontend
npm test -- --run
```

Observed: **17 passed in 2 files**. Coverage includes approved-with-open-exceptions, rejection, clean completion, awaiting review, direct URL reload, agent-failure display, server timeout, API unavailable/retry, the 60-request polling bound, audit and transfer links, and no duplicate start from refresh.

Frontend production build:

```powershell
Set-Location frontend
npm run build
```

Observed: **successful** (`tsc -b` and Vite production build).

Broader relevant backend regression:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_step9_flow.py tests/test_resolution.py tests/test_migrations.py tests/test_step10b_portal.py -q --tb=short
```

Observed: **50 passed**, one existing Starlette/httpx deprecation warning.

Complete backend regression:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

Observed: **470 passed**, one existing Starlette/httpx deprecation warning, **157.44 seconds**. No real Maestro run was launched for this UI increment.

## Render deployment and live acceptance

The original Step 10C backend and frontend were deployed through the existing Render-connected source. The 2026-11-22 presentation cleanup documented above is local and intentionally not deployed by this task. It requires no new environment variable. On the next Render deployment, startup migrates `/data/portal/transferiq.db` from registry v1 or v2 to v3 without resetting rows. `PORTAL_INVESTIGATION_ENABLED` and the existing webhook settings remain unchanged.

Latest portal verification, including global and transfer-specific Investigation History: focused portal backend **12 passed**; full backend **481 passed** with the existing Starlette/httpx warning; frontend **30 passed**; production build succeeded with 2,162 modules transformed. These are local automated results, not a new Maestro execution or Render deployment.

For authenticated lifecycle acceptance, use bounded reads before any new workflow:

1. verify `/health` returns 200 and `/portal` serves the new compiled asset;
2. authenticate and revisit the existing completed PEX URL to confirm the result survives deployment/reload;
3. verify its audit link returns the existing audit ledger;
4. only if another business-path check is required, launch one new portal run—do not repeatedly execute Maestro to test display-only behavior.

At the time of this Step 10C deployment, only the prior 1.0.1 approval was
available. This sentence is historical: solution 1.1.1 later completed
portal-triggered approval, rejection, and CLEAN controls.

After the user completed deployment, bounded verification on 2026-11-11 returned:

- `GET /health`: **HTTP 200**, `status=ok`, `database=ok`, `fictionalDemo=true`;
- `GET /portal`: **HTTP 200**;
- `GET /portal/transfers/TRF-1002`: **HTTP 200**;
- `GET /api/portal/session`: **HTTP 200**, `enabled=true`, unauthenticated as expected;
- deployed asset `assets/index-MWERZDmQ.js`: **HTTP 200**, matching the local Step 10C production build.

The deployed asset contains the Step 10C completion distinction, bounded-polling refresh message, and `View Audit Report` action. The user also supplied a screenshot of the deployed TRF-1002 portal page. This verifies deployment and public rendering. No authenticated PEX tracking response, completed Step 10C progress page, or new real Maestro execution ID was supplied, so end-to-end Step 10C lifecycle acceptance is not claimed.
