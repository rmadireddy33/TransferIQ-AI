# Step 5 test cases and observed evidence

All observations below are from 2026-11-01. PASSED means the named test layer passed, not that UiPath Cloud executed the Flow. No runtime run, instance ID, upload, deployment or published package exists from this step.

## Verification layers

| Layer | Status | Actual evidence |
|---|---|---|
| CLI availability/auth | PASSED | CLI updated from 1.195.1 to 1.204.0; `uip login status` returned Logged in |
| Automate scaffolding | PASSED | `flow init --automate --sdk-source`; `.maestro_automate`, `operate.json` profile Lite, project registered in `.uipx` |
| Source check / compile | PASSED | 0 errors, 0 warnings; 28 nodes, 27 edges |
| Product structural/expression validation | PASSED with reviewed warnings | Result Success, Data.Status Valid; 4 documented managed-HTTP `err()` typing diagnostics |
| Canvas formatting | PASSED | 28 nodes, 27 edges formatted |
| New isolated backend/Flow contracts | PASSED | `pytest tests/test_maestro_contract.py -q`: 57 passed, 1 upstream warning, 20.27s |
| Full regression suite | PASSED | `pytest -q`: **218 passed, 1 upstream Starlette warning in 49.39s**; isolated temporary SQLite only |
| Live local backend + emitted scripts/edges | PASSED | 10 cases below; persisted report at `data/verification/maestro-step5-local.json` |
| Tenant HTTP connection | BLOCKED | Refreshed all-folder HTTP listing returned no connections |
| Maestro runtime scenarios | BLOCKED | Backend not hosted; no public HTTPS URL or bound secure HTTP connection |

The build emitted four `EXPRESSION_DIAGNOSTIC` warnings at `GetTransferDetailsFailed`, `GetDeliveringPositionsFailed`, `GetReceivingPositionsFailed`, and `RunReconciliationFailed`. Each is the documented managed HTTP `err(step, 'status')` rewrite to `step.output.status`; the validator's type declaration omits that output on an error path. No other warnings were accepted. Source checks had an initial empty-arm warning, fixed by adding explicit configuration validation. An initial source review also found double-quoted failure labels caused by redundant JSON.stringify inside the SDK template; this was fixed before tests.

The CLI initially rejected `--automate`. Updating CLI/tool fixed the command. The first connection discovery encountered a network error; an escalated read-only refreshed lookup succeeded and found none. Product validation sometimes reported dynamic registry fetch failures, including IXP; no IXP/agent/connector activity is referenced by this built-in-node Flow. Product structure validation still returned Valid. This does not establish runtime connectivity.

## Transfer scenarios

Opening the designer added a response schema using `code`, exposing four extra status-field diagnostics against the SDK's `statusCode` examples. Validators were corrected to accept both documented envelopes, and both received regression coverage. The final rebuild/product validation returned to only the four reviewed HTTP error-envelope warnings. The designer also created empty evaluation templates under the project's `evals/`; no evaluation or LLM judge was run. An Integration Service tool update initially timed out in the restricted environment; the approved network-enabled retry aligned it to 1.204.0 and verified the connection-ping command.

Counts are `(directlyMatched, evidenceExplained, unresolvedCount, costBasisIssues)`.

| Input | Expected result | Isolated contract | Actual local HTTP | Maestro runtime |
|---|---|---|---|---|
| TRF-1001 | CLEAN; (7,0,0,0) | PASSED | PASSED | BLOCKED |
| TRF-1002 | INVESTIGATION_REQUIRED; (5,1,1,0); split evidence and unresolved shortage retained | PASSED | PASSED | BLOCKED |
| TRF-1003 | CLEAN; (0,1,0,0); verified identifier-mapping evidence retained | PASSED | PASSED | BLOCKED |
| TRF-1004 | Quantity CLEAN; (7,0,0,1); cost basis still requires review | PASSED | PASSED | BLOCKED |
| TRF-1005 | INVESTIGATION_REQUIRED; (0,0,1,0); unsupported quantity correction remains unresolved | PASSED | PASSED | BLOCKED |

The live verifier compared 15 complete transfer/source/staging responses before and after all runs: unchanged. Reconciliation can insert historical results/audit or update a reused run's last-requested time; no fixture is reset and no position or transfer lifecycle is modified.

## Failure scenarios

| Scenario | Expected | Local evidence | Maestro runtime |
|---|---|---|---|
| Unknown valid-shaped ID `TRF-NOT-FOUND` | FAILED at GetTransferDetails, HTTP404 | PASSED: actual backend request | BLOCKED |
| Invalid input `../bad` | FAILED before HTTP | PASSED: emitted validation/edges | BLOCKED |
| Missing API key | FAILED at RunReconciliation, HTTP401; one attempt | PASSED: actual backend request | BLOCKED |
| Backend unavailable | FAILED after bounded attempts; never reaches clean decision | PASSED: actual refused connection to OS-assigned local port | BLOCKED |
| No secure connection configured | FAILED / CONFIGURATION_REQUIRED before HTTP | PASSED: default artifact path | BLOCKED |
| HTTP 401/404/422/503/network error at each of four calls | Terminal FAILED, bounded attempts | PASSED: explicitly injected transport failures | BLOCKED |
| Malformed/missing/mismatched response | FAILED before RequiresInvestigation | PASSED: 17 malformed reconciliation variants plus invalid context cases | BLOCKED |
| HTTP timeout | FAILED; bounded retry | Shared network-error path exercised with injected transport failure; actual UiPath timeout not executed | BLOCKED |
| Source empty, wrong account/transfer, custody marker, truncated pages | FAILED before reconciliation where context is invalid | PASSED: isolated malformed-context fixtures | BLOCKED |

The harness's retry checks prove its local adapter policy and the emitted retry configuration; they do not measure UiPath retry scheduling. Failure fixtures are labeled test doubles and exist only in tests. The Flow contains no canned service responses or mock nodes.

## Repeat tests

```powershell
Set-Location C:\Projects\TransferIQ-AI
.\scripts\build-maestro.ps1
.\.venv\Scripts\python.exe -m pytest tests/test_maestro_contract.py -q
.\.venv\Scripts\python.exe -m pytest -q
# Requires the real local backend and its configured API_KEY in .env/environment:
.\.venv\Scripts\python.exe -m scripts.verify_maestro_local
```

After following [setup and secure connection binding](MAESTRO_STEP5_SETUP.md), debug each TRF-1001 through TRF-1005 with `--inputs '{"transferId":"TRF-1001"}'` (change only that ID). Assert the `result` fields and terminal branch against the table. For unknown/invalid input use the indicated IDs. For unauthorized testing use a dedicated test connection with an intentionally invalid credential; never disrupt the shared working connection. For unavailable/timeout testing use a controlled test backend and confirm no unrelated services are targeted. Record the actual instance ID, trace, observed result and PASSED/FAILED per run. Until then keep each runtime row BLOCKED.

The final suite includes 59 new Flow contract tests (the initial focused run had 57; two HTTP-envelope compatibility tests were added). No automatic corrections, approval workflow, IXP, agent, frontend or Railway deployment was tested or implemented.

## Files created or modified

- Created `maestro/TransferIQ_Reconciliation/`: CLI-generated solution manifest, AGENTS/CLAUDE workspace guides, project registration resources and nested Flow project.
- Created the nested project's `.flow-sdk/TransferIQ_Reconciliation.flow.ts`, five `.flow-sdk/scripts/*.js` bodies and `runtime.example.json`; generated `TransferIQ_Reconciliation.flow`, `project.uiproj`, `operate.json` and `.maestro_automate`. VS Code generated empty `evals/` templates, not runtime results.
- Created `scripts/build-maestro.ps1`, `scripts/configure-maestro.ps1`, `scripts/maestro-local-runner.mjs`, `scripts/verify_maestro_local.py`, and `tests/test_maestro_contract.py`.
- Created `docs/MAESTRO_STEP5_SETUP.md` and `docs/MAESTRO_STEP5_TEST_CASES.md`.
- Updated README.md, ARCHITECTURE.md, PROJECT_PLAN.md, AGENTS.md and .gitignore. No backend implementation/schema or existing financial fixture changed.
- Generated the ignored live evidence report `data/verification/maestro-step5-local.json`. No API key was copied into source or generated artifacts.
