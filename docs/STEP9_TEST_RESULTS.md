# Step 9 verification — 2026-11-06

## Executed local checks

Command: `.\.venv\Scripts\python.exe -m pytest tests/test_step9_flow.py tests/test_resolution.py tests/test_migrations.py -q --tb=short`

**34 passed**, one existing Starlette/httpx deprecation warning, 33.09 seconds. These include real isolated backend state and explicit test-double agent/human outputs. They are not real UiPath executions or human approvals.

Coverage: all four outcomes; TRF-1002 split acknowledgment and unresolved `-20` shortage; TRF-1004 basis case; TRF-1005 escalation; unchanged source/staging/underlying exceptions; invalid IDs/actions/evidence; duplicate preview/decision/execution; stale version/hash/data; capability scope; denied private privilege; event replay; plan quota; run expiry; public reads without capability leakage; restart persistence; SQL append-only protections; populated schema migration and registry migration. Graph tests cover every outcome port, independent result checks, tampered responses and controlled HTTP failures.

The initial complete run had **433 passed, 1 failed** (110.36 seconds). The failure was the existing graph assertion that all HTTP nodes retry once; it was updated to require zero retries on the three new review writes and preserve one retry on existing nodes. All original 416 tests remain; Step 8 tests explicitly cover their subgraph through independent agent validation, while new Step 9 tests cover the added continuation.

Final command: `.\.venv\Scripts\python.exe -m pytest -q --tb=short`. **447 passed**, one existing Starlette/httpx deprecation warning, **120.77 seconds**. This retains the original 416 cases and adds 31 Step 9 cases. Evidence: `data/verification/step9/pytest-final.txt`. No application tests were skipped or reported as live human approval.

Flow command: `uip maestro flow compile .flow-sdk/TransferIQ_Reconciliation.flow.ts -o TransferIQ_Reconciliation.flow` from the existing Flow project. Result: **Success, 80 nodes, 85 edges, zero compile errors/warnings**.

Product command: `uip maestro flow validate maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/TransferIQ_Reconciliation.flow --output json`. Result: **Success / Data.Status = Valid**, no warnings. The canonical artifact contains `TransferOperationsReview`, type `uipath.human-in-the-loop.quick-form`, version 1.0, and all four outcome edges. Local evidence is under ignored `data/verification/step9/`.

## Actual production response

One bounded request was made with no retry:

```http
POST https://transferiq-api.onrender.com/api/demo/runs/review
Content-Type: application/json

{}
```

Observed **HTTP 404**, body `{"detail":"Not Found"}`. This created no run. Step 9 routes require deployment; a deployed contract would reject this malformed request with 422. No rate-limit conclusion is drawn from this single request.

## Real Maestro acceptance status

| Test | Actual Step 9 result |
|---|---|
| TRF-1001 CLEAN, no form | Not run: new review-creation route absent on Render |
| TRF-1002 reaches Quick Form | Not run: same deployment blocker |
| TRF-1002 user approves; shortage remains open | Not run; no task generated/completed |
| Separate TRF-1002 user rejects | Not run; no task generated/completed |
| TRF-1004 missing-basis review | Not run |
| TRF-1005 unsupported shortage review | Not run |

Prior real Step 8 execution evidence remains in [STEP8_DEPLOYED_VERIFICATION.md](STEP8_DEPLOYED_VERIFICATION.md); it is not relabelled as Step 9 acceptance. No new UiPath execution ID, task ID, human approval, cloud disposition or audit success is claimed. The local Flow has not replaced the working cloud solution during these blocked tests.

Remaining actions: deploy the reviewed backend commit, verify the route, refresh/debug the validated Flow using the signed-in reviewer, capture each actual task identity, let the user complete it, then inspect the same execution and backend ledger/audit. See [deployment and manual completion instructions](STEP9_HUMAN_APPROVAL.md).
