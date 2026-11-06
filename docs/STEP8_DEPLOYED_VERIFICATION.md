# Step 8 deployed-backend verification

Verification on 2026-11-06 America/New_York targets `https://transferiq-api.onrender.com`. No financial reconciliation rules, rate limits, credentials, model configuration or IXP defaults were changed. The user deployed the backend; this verification does not claim to have performed a Render deployment.

## Deployed HTTP contract

The actual route is `GET /api/demo/runs/{runId}/investigation-references`, implemented in `backend/api/demo_execution.py`. It returns version 1.0 of the bounded, run-scoped `InvestigationReferences` contract: `runId`, `transferId`, fictional-demo marker, securities, identifier mappings and cost-basis records. It uses the synthetic run session, not the private database. Missing basis remains absent or null, never fabricated.

Each direct probe below was issued once, without automatic retries. Raw response bodies, statuses, headers and timestamps are saved under ignored `data/verification/step8-deployed-20261106/`.

| Request | Actual result |
|---|---|
| GET `/health` | 200 |
| GET `/openapi.json` | 200; declares the supplemental-reference GET and `InvestigationReferences` response |
| POST `/api/demo/runs`, transferId TRF-1002 | 201; new isolated run created |
| GET supplemental references for that new run | 200; contractVersion 1.0; TRF-1002; 7 securities, 0 identifier mappings, 7 basis records |
| GET supplemental references for `DEMO-00000000000000000000000000000000` | 404; `detail.code=not_found`, `detail.message=Unknown demo run` |
| POST `/api/demo/runs`, transferId TRF-NOT-FOUND | 422; Pydantic `literal_error` for the allowlisted transfer IDs; no Retry-After |

The supplemental endpoint is therefore deployed and no longer returns route-not-found for a valid run. The negative 404 is an intentional resource lookup failure, not a missing route. Unknown **run** IDs and unsupported **transfer** IDs are different contracts. Expired runs have a separate 410 path in source, but no expiry test was performed against production in this session.

OpenAPI still reports application version `0.4.0` and the service does not expose a commit/build SHA. Successful route and payload verification confirms the Step 8 capability is deployed; it does not independently identify the exact GitHub commit or Render deployment ID.

## Previous HTTP 429 investigation

The saved real Maestro instance `29fac6e6-7889-49e4-bdd1-46d5a951bafa` failed at CreateDemoRun. Its HTTP error envelope records a backend response on 2026-11-06 at 04:49:51 UTC with HTTP 429, `Retry-After: 22`, and body `detail.code=rate_limited`, `message=Public request limit exceeded`. The response also identifies the Render origin as uvicorn. This was not a missing reference endpoint, an AI model failure or the separate `demo_quota`/`demo_storage_quota` capacity errors.

The matching source path is `PublicLimits` in `backend/api/public_limits.py`, before request-body validation. It applies a shared 60-second request window using ASGI peer identity. Source defaults are 60 public requests/client/minute and 300 globally; POST run creation also has a fixed budget of 5/client/minute and 20 globally. Production environment overrides for the general budgets were not inspected. Invalid payloads and retries can consume the creation budget because this middleware runs before Pydantic rejects the input. The same error code covers general and creation budgets.

The historical trace does not contain limiter counters, earlier peer requests or each underlying HTTP attempt. It establishes the limiter rejection but cannot distinguish which cap was reached or establish why that budget was exhausted. Shared proxy/egress identity and retry behavior are possibilities, not proven causes. No claim is made that a single visible Flow run alone exceeded the budget.

Current bounded probes returned the intended 404 and 422. There was no deliberate saturation test, retry storm, raised quota or rate-limit bypass. The existing Flow still declares one bounded retry for HTTP nodes; no extra debug retry loop was added. A 422 captured inside Maestro for the unsupported-transfer scenario remains an older verification gap; this session verifies that negative response directly over HTTPS and tests the unknown-run GET directly.

## Regression and static validation

- `.\.venv\Scripts\python.exe -m pytest -q --tb=short`: **416 passed**, 1 upstream Starlette/httpx deprecation warning, 110.97 seconds. Existing financial, immutability, authorization, idempotency, isolation, persistence and restart checks are included.
- From the Flow project: `uip maestro flow check .flow-sdk/TransferIQ_Reconciliation.flow.ts --source`: 0 errors, 0 warnings.
- `uip maestro flow validate TransferIQ_Reconciliation.flow --output json`: Valid; no warnings reported.

The installed CLI automatically refreshed itself and its skills during the first validation command; validation then completed successfully. Resource refresh reports the existing `ImplicitConnection` catalog advisory. This is separate from Flow validation and is retained in the evidence. No TransferIQ authentication binding was added.

The existing Studio Web solution was exported before debug. Both cloud and local artifacts contained 49 nodes with identical node inputs, and no cloud-only nodes. Live debug uses the existing solution and explicitly supplies `enableIXP=false` with no PDF. See the live results below for actual runtime evidence.

## Actual Maestro executions

Studio Web: [TransferIQ_Reconciliation](https://cloud.uipath.com/rmadireddy33/studio_/designer/1b2fbdc5-a860-4635-b7ea-920ca1b7fe56?solutionId=76aa4adb-4a5a-4fde-0921-08df3690f20b)

| Input | Instance ID | Runtime / business result | Agent / IXP |
|---|---|---|---|
| TRF-1002 | `370a5354-b242-4fc1-a298-4372f8234725` | Completed / INVESTIGATION_COMPLETED | Real agent completed; IXP not executed |
| TRF-1001 | `eb959355-1ceb-45d3-983d-4e1f093b8195` | Completed / CLEAN | Both skipped |

| HTTP node | TRF-1002 | TRF-1001 |
|---|---:|---:|
| CreateDemoRun | 201 | 201 |
| GetTransferDetails | 200 | 200 |
| GetDeliveringPositions | 200 | 200 |
| GetReceivingPositions | 200 | 200 |
| RunReconciliation | 201 | 201 |
| GetCorporateActionReference | 200 | Not executed |
| GetInvestigationReferences | 200 | Not executed |

The actual TRF-1002 agent `inputs.JobArguments` contains a serialized context that was parsed and compared for equality against the captured reference responses. All 7 securities, 0 applicable identifier mappings, 7 basis records and 1 corporate-action record matched. Empty mappings are a successful empty reference result, not missing API evidence. The actual agent input and final report both have `missingEvidence=[]`; output validation has `validationErrors=[]`. The document status is `NOT_PROCESSED_IXP_DISABLED`.

The SEC-103 finding is CORPORATE_ACTION_TIMING with VERIFIED evidence and recommendation NORMALIZE_COMPARISON. It cites the actual `CA-2026-081` record plus source/staging/exception IDs. That reference establishes a 2-for-1 split effective 2026-08-10; backend source quantity 40 and receiving/normalized quantity 80 agree with the existing explained exception.

SEC-104 remains QUANTITY_MISMATCH, UNRESOLVED, source/expected 120 versus receiving 100, difference `-20`. The agent uses INCOMPLETE evidence and recommends INVESTIGATE_POSITION_SHORTAGE. `humanReviewRequired=true`, `correctionsApplied=0`, and `transferCompleted=false`. INVESTIGATION_COMPLETED describes successful investigation and output validation, not transfer completion or resolution of the shortage.

TRF-1001 retained 7 directly matched positions and CLEAN. For both runs, follow-up anonymous source and staging GETs returned 200 and exactly matched their pre-reconciliation trace responses. Audit GETs returned 200 with zero corrections. Both runs had zero incidents.

## Commands and retained evidence

```powershell
$env:PATH = "$env:APPDATA\npm;$env:PATH"
uip solution resources refresh --solution-folder maestro/TransferIQ_Reconciliation --output json
uip maestro flow debug maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation --inputs '@data/verification/step8-deployed-20261106/input-1002.json' --timeout 600 --output json
# Refresh resources again, then run the separate clean scenario:
uip solution resources refresh --solution-folder maestro/TransferIQ_Reconciliation --output json
uip maestro flow debug maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation --inputs '@data/verification/step8-deployed-20261106/input-1001.json' --timeout 600 --output json
.\.venv\Scripts\python.exe -m scripts.summarize_maestro_debug data/verification/step8-deployed-20261106/debug-1002.json data/verification/step8-deployed-20261106/debug-1001.json --verify-backend-url https://transferiq-api.onrender.com --output data/verification/step8-deployed-20261106/summary.json
```

Input files explicitly contain `enableIXP:false`. Debug runs were sequential and each scenario was run once. Production probes used no automatic retry wrapper. Logs and raw responses are retained in ignored `data/verification/step8-deployed-20261106/`, including `agent-input-verification.json`, `summary.json`, `references-probe.json`, `unknown-run.json`, `unknown-transfer.json` and the two complete debug envelopes. The prior 429 trace is preserved for comparison under that directory's `.local/investigations/raw/`.

The supplemental-reference blocker is cleared. Remaining limitations are the unverified exact deployed commit ID, the unproven historical budget-consumption cause of the 429, and the older absence of an in-Maestro unsupported-transfer 422 capture. No current requested scenario is blocked by supplemental references. IXP remains disabled; no extraction, approval, correction, settlement or additional scenario execution is claimed for this verification session.
