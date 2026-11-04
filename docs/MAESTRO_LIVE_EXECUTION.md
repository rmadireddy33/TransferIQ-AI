# Real Maestro Automate execution evidence

Executed on 2026-11-02 America/New_York (2026-11-03 UTC) against `https://transferiq-api.onrender.com`. These are **actual UiPath cloud debug runs**, not the local graph harness or precomputed samples.

Open the uploaded Flow in [Studio Web](https://cloud.uipath.com/rmadireddy33/studio_/designer/1b2fbdc5-a860-4635-b7ea-920ca1b7fe56?solutionId=76aa4adb-4a5a-4fde-0921-08df3690f20b). The link requires access to the owner's UiPath environment; it is not an anonymous public workflow trigger. Judges importing into their own tenant use their own sign-in and permissions, without TransferIQ credentials.

## Observed cloud results

| Input | Actual final result | Actual terminal branch | Direct / explained / unresolved | UiPath instance ID |
|---|---|---|---|---|
| TRF-1001 | CLEAN | CleanReconciliation | 7 / 0 / 0 | `1911673e-4ba8-4897-a9fe-365ff3900a3e` |
| TRF-1002 | INVESTIGATION_REQUIRED | InvestigationRequired | 5 / 1 / 1 | `f1e9ded6-2235-46bc-a34e-6a5174f00233` |
| TRF-1005 | INVESTIGATION_REQUIRED | InvestigationRequired | 0 / 0 / 1 | `7408e23d-49f6-482e-95db-8c5eee1023f0` |
| TRF-NOT-FOUND, initial attempt | FAILED, HTTP 429 | CreateDemoRunFailed | Not calculated | `87010488-4c21-4ff5-a25a-ad3cb72655c4` |
| TRF-NOT-FOUND, retry after limit window | FAILED, HTTP 429 | CreateDemoRunFailed | Not calculated | `6470234e-f44b-4764-afda-5dce41e22b8b` |

For all three valid transfers, the recorded HTTP node responses were:

| Node | Method | Actual status |
|---|---|---:|
| CreateDemoRun | POST | 201 |
| GetTransferDetails | GET | 200 |
| GetDeliveringPositions | GET | 200 |
| GetReceivingPositions | GET | 200 |
| RunReconciliation | POST | 201 |

`RequiresInvestigation` executed in each valid case and the traced terminal agrees with the normalized counters. No correction was applied. Later anonymous GETs were compared with the source/staging responses captured before reconciliation in each real trace: both remained identical in all three cases. Audit GETs returned 200 and `correctionsApplied=0`.

The initial invalid-ID cloud attempt returned a real backend `rate_limited` response (429, Retry-After 23 seconds) and safely stopped at CreateDemoRunFailed. Transfer/position/reconciliation nodes did not execute and no CLEAN branch was taken. This first attempt is rate-limit failure evidence, not proof that the invalid-ID validator ran. An earlier direct anonymous HTTPS/local-graph check of the same invalid ID returned 422 and FAILED. Both layers are distinguished here.

One subsequent cloud retry after the earlier rate-limit window also returned 429. **Remaining limitation:** the unknown-ID validation response (422) has not been captured as the final HTTP response in Maestro; its two traces prove safe handling of 429 instead. No rate limits were disabled or raised to make a test pass. The available trace establishes the backend rate-limit response, but does not establish which upstream attempts exhausted its budget. Valid-scenario execution has no remaining blocker.

UiPath reports `finalStatus=Completed` even for a handled FAILED business result because the explicit failure terminal completed normally. Always inspect `result.workflowOutcome`; do not interpret the CLI's Success envelope as a clean reconciliation.

## Contract and validation

Only one `.flow` exists in the repository; it was reused without recreating the project. The existing 28-node/27-edge artifact already met the requested public contract, and no business algorithm or Flow source change was needed for these runs.

- Manual Trigger supplies dynamic `transferId`.
- All five HTTP nodes use `authentication=manual`, `ImplicitConnection`, null connection resource/folder references, and no Authorization or X-API-Key header. `Idempotency-Key` is an automatically generated non-secret retry identifier, not authentication.
- The deployed OpenAPI specification declares no security requirement for the run endpoints. Only run creation requires the non-secret idempotency header.
- Returned demo run ID, source account and destination account drive downstream URLs. Requests and responses are real; `simulations.json` remains empty.
- Existing normalization validates actual status codes, transfer identity, counters, evidence, exception ownership, complete position lists and staging semantics. Existing Decision nodes route CLEAN, INVESTIGATION_REQUIRED and FAILED.
- `uip maestro flow validate ... --output json` returned **Valid**, with no Flow warnings. The registry lookup logged inability to fetch unused IXP nodes; no IXP node is in this Flow.
- Resource refresh completed with zero resource contributions and a CLI warning that Flow resource contributions were not inspected. This project has no external connection bindings; the recorded cloud runs verify that manual transport works. The warning is retained rather than represented as a clean resource-inspection result.

## Verification commands and local evidence

```powershell
uip maestro flow validate .\maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation\TransferIQ_Reconciliation.flow --output json
.\.venv\Scripts\python.exe -m pytest tests/test_maestro_contract.py tests/test_deployment.py -q --tb=short
```

Regression result: **129 passed, 0 failed, 1 upstream Starlette/httpx deprecation warning, 72.83 seconds**. The real HTTP verifier now includes TRF-1005 alongside TRF-1001, TRF-1002 and an invalid ID. Deployment tests ran that verifier against an actual isolated Uvicorn server. No tests used the development database.

Full cloud envelopes are retained locally in ignored `data/verification/maestro-live/debug-1001.json`, `debug-1002.json`, `debug-1005.json`, `debug-invalid.json`, and `debug-invalid-retry.json`. These contain actual node outputs, instance IDs and timestamps. `summary.json` contains the first four runs and anonymous post-run position checks; `summary-final.json` includes all five cloud attempts. The helper `scripts/summarize_maestro_debug.py` handles both JSON encodings and the real error envelope (`error=true`, HTTP status in response). It never invents missing node execution data.

The UiPath debug CLI uploaded the existing solution and updated its `.uipx` SolutionId automatically to the returned cloud solution ID. No `.uipx` was hand-edited. No Render deployment, permanent Orchestrator process publication, IXP, agent or human-approval integration was performed.

## Run manually in Studio Web

1. Open the Studio Web link above with an authorized UiPath account. Open `TransferIQ_Reconciliation` on its **Flow** canvas.
2. Use Debug/Run and provide the Manual Trigger input `transferId` as `TRF-1001`, `TRF-1002`, or `TRF-1005`. Do not create an HTTP connection or enter a TransferIQ API key.
3. Wait for completion, then inspect `NormalizeReconciliation`, `RequiresInvestigation`, the terminal node, and `result`. For a negative test use `TRF-NOT-FOUND`; inspect CreateDemoRunFailed and `httpStatus`.
4. Use a fresh run for each intended execution. Each creates an isolated synthetic backend run; retries within a run reuse its non-secret idempotency key. Respect 429 Retry-After and avoid rapid repeated submissions.

For your own tenant, use `uip login`, then from the repository root:

```powershell
uip solution resources refresh --solution-folder .\maestro\TransferIQ_Reconciliation --output json
uip solution upload .\maestro\TransferIQ_Reconciliation --output json
# Open the returned DesignerUrl in your own tenant.
```

Do not force-replace an unrelated solution. The [judge setup guide](ZERO_CREDENTIAL_DEMO.md) covers backend reproduction, quotas, data retention and the distinction between zero TransferIQ credentials and UiPath tenant access. Public backend run/PDF retention is 24 hours by default; local saved trace evidence persists independently. Future IXP, agents and human tasks still need their own tenant resources and permissions and are outside this reconciliation Flow.
