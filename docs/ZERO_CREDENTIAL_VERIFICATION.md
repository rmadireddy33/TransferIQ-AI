# Anonymous demo execution verification — 2026-11-02

This revision is implemented locally. It has **not** been deployed to Render or executed in the UiPath cloud runtime. Local graph results are not represented as Maestro instance traces.

## Executed checks

| Command/check | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests/test_demo_execution.py -q --tb=short` (initial focused check) | 10 passed; 1 upstream Starlette deprecation warning |
| `.\.venv\Scripts\python.exe -m pytest -q --tb=short` (first regression run) | 340 passed, 1 failed: concurrency test incorrectly required every initial request to complete before the bounded busy timeout |
| Same complete suite after adding explicit busy/retry and quota coverage | **349 passed**, 0 failed, 1 upstream Starlette warning, 106.69 seconds |
| `.\.venv\Scripts\python.exe -m pytest tests/test_maestro_contract.py tests/test_deployment.py -q --tb=short` after the final POST header change | **129 passed**, 0 failed, 1 upstream Starlette warning, 33.81 seconds; includes real HTTP/local graph and restart checks |
| `.\scripts\build-maestro.ps1` after final explicit JSON POST headers | Source check/compile: 0 errors, 0 warnings. Product validate: **Valid**, no Flow warnings. 28 nodes, 27 edges. |
| `python -m scripts.verify_render_maestro_contract` | Real anonymous HTTPS: `/health` 200; `/openapi.json` available but lacks `/api/demo/runs`. Report BLOCKED and command nonzero; no synthetic run created on Render. |
| `uip login status --output json` | Connected UiPath login available. Personal account/tenant details are deliberately omitted from this report. |
| Actual UiPath TRF-1001/TRF-1002 execution | **Not executed**: hosted backend still lacks the new public run routes. No cloud upload, instance ID, Decision trace or successful cloud outcome is claimed. |
| PowerShell parser check for `scripts/configure-maestro.ps1` | Syntax valid; helper accepts only an HTTPS host override, no connection ID or secret |

The product validator also logged `Failed to fetch IXP nodes` while loading the tenant node catalog. It returned Valid for this Flow, which contains no IXP node. This is not an IXP integration test.

The failed concurrency assertion was corrected to test the documented contract: 503 is a safe busy response; retrying with the same request ID after the first run finishes must return the one existing run. The implementation's bounded lock was preserved. Additional tests explicitly exercise the busy response, creation rate limit, storage admission quota and malformed run responses.

## What the tests exercised

All tests use isolated temporary storage, never the development database. Anonymous requests send no Authorization or X-API-Key header.

- Actual FastAPI requests for every TRF-1001–TRF-1005 scenario, using the existing engine; transfer/source/staging reads, reconcile, result/exception retrieval, document list, real PDF download/hash and sanitized audit.
- Expected direct/explained/unresolved counts: 1001 `(7,0,0)`, 1002 `(5,1,1)`, 1003 `(0,1,0)`, 1004 `(7,0,0)` with independent cost-basis issue, 1005 `(0,0,1)`.
- Concurrent run/reconciliation idempotency, conflicting idempotency keys, isolated run document IDs and account scope, unchanged source/staging positions and byte-for-byte logical private database contents.
- Restart persistence, expiry response and scoped expired-run cleanup, protected private requests, absent public administrative/reset/upload/correction/approval/trigger routes, unknown IDs, bounded/chunked bodies, quotas and disable flag.
- Real Uvicorn subprocess startup and restart with actual TCP HTTP requests. The local graph harness reached `CleanReconciliation` for TRF-1001 and `InvestigationRequired` for TRF-1002. Their HTTP calls returned create 201, context GETs 200 and reconcile 201. Reconcile replay returned 200 with the same reconciliationRunId. Exception/document/audit reads and actual PDF download returned 200. Unknown transfer creation returned 422 and the graph ended FAILED.
- Emitted Flow contract/error tests cover both HTTP status envelope shapes, 401/403/404/422/503, transport failures, malformed responses and validation failure branches. Failure injection exists only in tests; the shipped Flow contains no fake API responses.

## Implementation inventory

- New backend modules: `backend/api/demo_execution.py`, `backend/services/demo_runs.py`.
- Backend integration/configuration: `backend/main.py`, `backend/core/config.py`, `backend/api/public_limits.py`, `.env.example`.
- New test module: `tests/test_demo_execution.py`; expanded `tests/test_judging.py`, `tests/test_maestro_contract.py`, `tests/test_deployment.py`.
- Existing Flow SDK source, new `validate-demo-run.js`, normalized result's `demoRunId`, and regenerated `TransferIQ_Reconciliation.flow`.
- Verification/configuration helpers: `scripts/verify_public_demo.py`, existing local/Render verification entry points, `scripts/maestro-local-runner.mjs`, `scripts/configure-maestro.ps1`.
- Updated README, architecture, project plan, development guidelines, Render/judging/Maestro guides; new `ZERO_CREDENTIAL_DEMO.md` and this report.

No business reconciliation algorithm, custody schema, approval/correction rule, private API credential, dependency list, UiPath tenant resource, or deployed Render service was changed. The new anonymous wrapper intentionally calls existing backend services with isolated seeded data.

## Remaining acceptance

Manually deploy the revision using [Render instructions](RENDER_DEPLOYMENT.md). Run the anonymous verifier against the hosted URL; then run the supplied Automate Flow in an entitled UiPath tenant using TRF-1001 and TRF-1002 and inspect its real node statuses/Decision branches. Follow [exact judge setup and remaining dependencies](ZERO_CREDENTIAL_DEMO.md). IXP, Autonomous Agents and human tasks remain future integrations.
