# Step 8 verification

These are the initial implementation results. The later [post-deployment verification](STEP8_DEPLOYED_VERIFICATION.md) supersedes the supplemental-reference deployment blocker: HTTP 200 and TRF-1002 INVESTIGATION_COMPLETED are now verified.

Executed 2026-11-05 America/New_York (cloud traces are dated 2026-11-06 UTC). All live runs use `enableIXP=false` and omit the optional PDF. The existing solution was reused; a cloud export and local baseline were preserved under ignored `data/verification/step8/` before debug uploaded the revised Flow. The cloud/local baseline differences were designer HTTP metadata and equivalent expression formatting, not different business operations.

## Actual Maestro results

[Studio Web Flow](https://cloud.uipath.com/rmadireddy33/studio_/designer/1b2fbdc5-a860-4635-b7ea-920ca1b7fe56?solutionId=76aa4adb-4a5a-4fde-0921-08df3690f20b)

| Scenario | Instance ID | Observed outcome |
|---|---|---|
| TRF-1001 | `dc95e03c-c5df-4291-93ee-34a30f828b9c` | CLEAN; agent and IXP skipped; 7 directly matched positions |
| TRF-1002 | `85a4b8fd-7f4a-4659-9994-96f33cce146e` | Real agent completed; output validation passed; INVESTIGATION_REVIEW_REQUIRED because supplemental-reference GET returned 404 |
| TRF-1004 | `de5d8ab8-d54b-428c-9085-4de1af60c1d5` | Real agent identified SEC-007 COST_BASIS_MISSING and recommended OPEN_COST_BASIS_CASE; validation passed; report requires review |

TRF-1005 also completed in the real runtime (instance `ba17954d-9f02-411d-964b-e69fd42b8fbd`). The agent preserved SEC-301's 20-unit shortage, classified evidence INCOMPLETE and recommended INVESTIGATE_POSITION_SHORTAGE. Validation passed and the final report requires review because supplemental references were unavailable.

The real unknown-ID attempt (instance `29fac6e6-7889-49e4-bdd1-46d5a951bafa`) returned FAILED with HTTP 429 at CreateDemoRunFailed. Neither agent nor IXP ran. As in Step 5, the expected unknown-ID 422 response remains masked by public rate limiting in Maestro; local backend/HTTP regression tests verify 422. No rate limit was relaxed and no repeated equivalent cloud attempt was made.

TRF-1002's actual agent input included the transfer, seven source positions, seven receiving staging positions, reconciliation IDs/results, two actual exception IDs, the independently fetched verified `CA-2026-081` split record, indexed evidence IDs and explicit missing-reference status. The emitted runtime argument `SerializeInvestigationContext__output` carried the serialized context; the agent did not receive a literal unresolved prompt placeholder.

The actual SEC-103 finding cited `CA-2026-081`, source/staging position IDs and its real exception ID. It explained the 2-for-1 split effective 2026-08-10 between the source snapshot 2026-08-01 and receiving snapshot 2026-08-15: backend source 40, expected/receiving 80. It recommended `NORMALIZE_COMPARISON` with VERIFIED evidence. The SEC-104 finding retained source/expected 120 versus receiving 100, cited actual position/exception IDs, classified the cause INCOMPLETE and recommended `INVESTIGATE_POSITION_SHORTAGE`. Its unresolved exception remained unchanged. The summary explicitly said IXP document extraction was skipped. Neither finding granted correction authority.

TRF-1004 followed the new cost-basis investigation branch even though all quantities matched. Its agent separated the missing SEC-007 cost basis from position matching, used INCOMPLETE evidence and required human review. It did not invent a cost-basis amount.

For TRF-1002, TRF-1004 and TRF-1005, corporate-action GET returned 200. The new `/investigation-references` GET returned actual 404 from the deployed backend. Its failure path continued to the agent with empty supplemental collections and an explicit `missingEvidence` entry. A successful agent response therefore does not imply a fully available evidence integration: final workflow outcome remains review-required. `investigationStatus=COMPLETED` describes agent/validation completion only.

Anonymous follow-up source/staging GETs were compared with the exact pre-reconciliation trace responses for all four valid scenarios (TRF-1001/TRF-1002/TRF-1004/TRF-1005): identical. Audit GETs confirmed `correctionsApplied=0`. There were no unhandled incidents in these runs. Evidence lives in ignored `data/verification/step8/debug-*.json` and `summary.json`; full payloads are retained locally, not pasted into source-controlled logs.

## Local tests and product validation

| Check | Observed result |
|---|---|
| `uip maestro flow check .flow-sdk/TransferIQ_Reconciliation.flow.ts --source` from the project directory | 0 errors, 0 warnings |
| `uip maestro flow compile .flow-sdk/TransferIQ_Reconciliation.flow.ts -o TransferIQ_Reconciliation.flow` | 49 nodes, 51 edges; real agent sidecar emitted |
| `uip maestro flow validate TransferIQ_Reconciliation.flow --output json` | Valid; no warnings reported |
| `.\.venv\Scripts\python.exe -m pytest -q --tb=short` | **416 passed**, 1 upstream Starlette/httpx deprecation warning, 100.72 seconds |

The final error-report refinement also keeps cost-basis exceptions in unresolvedExceptions if the agent fails; this was unit-tested, while actual provider failure/timeout remains test-double coverage only. The final source check and product validation were rerun after that refinement with no warnings.

The full suite covers existing backend/API authentication, reconciliation and financial precision, database immutability, idempotency, migrations, restart/persistence, private PDFs, run isolation and deployment smoke tests. No private financial algorithm was changed. The existing local graph verifier was updated to expect agent failure when no explicitly supplied test double exists; it cannot claim AI success.

New/updated test coverage:

| Scenario | Verification boundary |
|---|---|
| TRF-1001 CLEAN with no file | Real cloud plus local graph; no agent/IXP invocation |
| TRF-1002 split plus unresolved shortage | Real cloud plus explicitly labelled agent test doubles |
| TRF-1004 separate cost-basis case | Real cloud plus test double and actual isolated backend records |
| TRF-1005 unresolved mismatch | Real cloud plus local graph/test double |
| Invalid/empty transfer ID, unexpected/incomplete reconciliation, missing exceptions | Local graph and existing backend tests; safe FAILED result |
| Reference 404/503/transport failure | Test-injected failures; supplemental-reference 404 also observed live |
| Agent unavailability/transport timeout | Explicit injected failure through AgentFailed; no claim of an actual provider outage |
| Wrong transfer/exception/security/evidence IDs, cross-security evidence | Independent validator rejects test double output |
| Empty/duplicate/missing findings, unknown fields, malformed JSON-string output | Independent validator rejects test double output |
| Unsupported action, unsupported normalization, high confidence overriding evidence | Rejected; original unresolved records preserved |
| Conflicting evidence status | Review-required; no financial reclassification |
| Prompt injection text in reference data | Injected text cannot authorize an unsupported action; no live adversarial model robustness claim |
| Missing optional file or supplied file with IXP disabled | Agent path continues; extraction never invoked |
| IXP enabled with absent file/unconfigured setup-stop | Local negative route only; no real extraction claimed |
| Supplemental endpoint | Real isolated TestClient reads, private-database snapshot unchanged, foreign run rejected, mutation methods denied, missing basis remains absent |

Initial verification found and corrected a test assumption about absent basis records and two stale regression expectations (local-agent outcome and public GET inventory). The first debug command rejected a BOM-prefixed JSON input before creating a run; the input was rewritten as UTF-8 without BOM. Final results above are from the corrected sources. The sandbox could not launch Windows Store Python with test arguments; approved execution of the existing environment ran the recorded suite. No test output was fabricated.

## Reproduce and inspect

```powershell
$env:PATH = "$env:APPDATA\npm;$env:PATH"
# From repository root:
.\scripts\build-maestro.ps1
.\.venv\Scripts\python.exe -m pytest -q --tb=short
uip solution resources refresh --solution-folder maestro/TransferIQ_Reconciliation --output json
uip maestro flow debug maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation --inputs '@input.json' --timeout 600 --output json
.\.venv\Scripts\python.exe -m scripts.summarize_maestro_debug data/verification/step8/debug-1001.json data/verification/step8/debug-1002.json --verify-backend-url https://transferiq-api.onrender.com --output data/verification/step8/summary.json
```

Use a UTF-8 BOM-free input file containing the intended scenario and `enableIXP:false`. Inspect the recorded response, not just the CLI exit code or `finalStatus=Completed`; handled review/failure branches also complete successfully in Maestro. Respect demo quotas/Retry-After. Do not rerun a cloud debug merely to reread its output.

Resource refresh returned an advisory that `ImplicitConnection` is absent from the resource catalog. No TransferIQ connection was created; the real Manual HTTP executions succeeded without credentials. IXP permissions remain blocked and no real Extract model was provisioned. Full evidence availability and a live `INVESTIGATION_COMPLETED` report require deploying the supplemental-reference endpoint to Render and rerunning the scenario. No backend deployment, permanent Orchestrator publication, approval or correction was performed.
