# Current Step 9 verification

The manually created form and repaired original approval path now work end to end. Real TRF-1002 approval and rejection are VERIFIED_DEMO_STATE with SEC-104 still unresolved at -20; original TRF-1001 is CLEAN. Full local suite: 460 passed. See [current verification and remaining live cases](STEP9_MANUAL_FORM_VERIFICATION.md). The earlier deployment and 400-error records below are historical.

# Step 9 verification — 2026-11-06

**November 9 follow-up:** fixed the observed top-level agent `requiresHumanReview=null` contract failure. The corrected real TRF-1002 run `de7e148a-2147-426f-a6ae-f3a8aad544e7` returned INVESTIGATION_COMPLETED with the required flag true, default reviewer resolved, and preview HTTP 200, then still failed at Quick Form with HTTP 400 / 170000. Canonical product validation passed; **50 focused tests passed in 19.70 seconds** after file-overwrite interference stopped. Independent backend GETs returned 200, confirming unchanged positions, no decision/dispositions and SEC-104 unresolved at -20. No human task/completion is claimed. See [correlated runtime evidence and correction status](STEP9_NOV9_DATA_DIAGNOSIS.md). Counts below describe earlier artifacts, not the current minimal candidate's full-suite coverage.

## Post-redeployment live results

Backend redeployment is now verified. `/health` returned **200** (`status=ok`, `database=ok`); `/openapi.json` returned **200** and includes the Step 9 review/preview routes. The same malformed review POST now returns **422** (missing `Idempotency-Key` and `transferId`), replacing the earlier 404 below. The actual Maestro review run then received **201** from run creation and **200** from plan preview.

Studio Web: https://cloud.uipath.com/rmadireddy33/studio_/designer/1b2fbdc5-a860-4635-b7ea-920ca1b7fe56?solutionId=76aa4adb-4a5a-4fde-0921-08df3690f20b

| Actual execution | Observed result |
|---|---|
| TRF-1001 — `81ef435a-497c-4c06-82a1-6141646cf771` | **Completed / CLEAN**, IXP disabled; no human-review path taken. CLI retained one internal post-subprocess gateway as InProgress despite terminal Completed; no incident was returned. |
| TRF-1002, current-user email — `0f22d0f0-6d7e-4175-92e0-186bfdb5707b` | Real agent **INVESTIGATION_COMPLETED**, missingEvidence empty, validated plan preview **200**; then Quick Form creation **Faulted**, HTTP **400**, incident **170000**, `Failure in the AppTasks request`. |
| One bounded comparison using the same user's verified GUID — `55fb4761-a528-4302-9146-55103d6b7519` | Real agent and preview succeeded again; same Quick Form **400 / 170000**. No further equivalent launches. |

First run: `DEMO-441dbac6f1454ed18b0de575516ad57a`, plan `PLAN-960a6869-0a71-49a0-804a-6d6bf301d820`, reconciliation `REC-6a86aee2-ce6e-487e-91b0-19f84ec56401`. Real agent/form input includes verified 2-for-1 corporate action `CA-2026-081` for SEC-103 and the unresolved SEC-104 `120` expected versus `100` receiving shortage. Planned actions are ACCEPT_VERIFIED_EXPLANATION and ESCALATE_TO_TRANSFER_OPERATIONS respectively.

Independent production GET verification returned **200**: `PREVIEWED`, null humanReviewOutcome, zero dispositions, `NOT_VERIFIED`, `positionsUnchanged=true`, `transferCompleted=false`, SEC-104 `UNRESOLVED`, difference `-20`. Audit GET returned **200**, containing only `PLAN_PREVIEWED`. The comparison run's plan `PLAN-1d5936af-bce4-4e7d-93a8-b93ef6718db2` in `DEMO-10737d01c512476895ed137f39d981b1` has the same unchanged/unreviewed state.

The task incident supplies no field-level reason: its runtime error has HTTP 400 with `Response=null`. The current user is listed as assignable in the same debug folder. Email→GUID did not resolve the error. A folder-scoped administrative Action Center query found no TransferOperationsReview task. **No actual human task or completion was observed; approval/rejection execution remains unverified.** No financial state was changed. The exact rejected task-service property/root cause is **unconfirmed**; do not label this a demonstrated permission or platform defect.

TRF-1004/TRF-1005 live human-review runs and TRF-1002 approve/reject runs remain blocked by task creation and were not launched repeatedly. Existing local results below remain valid; no implementation changes or new pytest run occurred in this deployment-verification follow-up. Product Flow validation was rerun successfully without warnings before live execution. Resource refresh emitted the known `ImplicitConnection` catalog advisory; the actual manual-auth HTTP requests succeeded.

Sanitized live outputs: ignored `data/verification/step9/live/`; task diagnostics: ignored `maestro/TransferIQ_Reconciliation/.local/investigations/`. Runtime capabilities were redacted from stored variable responses. For UiPath diagnosis, use the first incident `624faba8-3abd-4f4b-935e-f135138dca41`, trace `0f22d0f06d7e417592e0186bfdb5707b`, and the exact node/instance above; do not share raw headers or capabilities.

## Executed local checks

Command: `.\.venv\Scripts\python.exe -m pytest tests/test_step9_flow.py tests/test_resolution.py tests/test_migrations.py -q --tb=short`

**34 passed**, one existing Starlette/httpx deprecation warning, 33.09 seconds. These include real isolated backend state and explicit test-double agent/human outputs. They are not real UiPath executions or human approvals.

Coverage: all four outcomes; TRF-1002 split acknowledgment and unresolved `-20` shortage; TRF-1004 basis case; TRF-1005 escalation; unchanged source/staging/underlying exceptions; invalid IDs/actions/evidence; duplicate preview/decision/execution; stale version/hash/data; capability scope; denied private privilege; event replay; plan quota; run expiry; public reads without capability leakage; restart persistence; SQL append-only protections; populated schema migration and registry migration. Graph tests cover every outcome port, independent result checks, tampered responses and controlled HTTP failures.

The initial complete run had **433 passed, 1 failed** (110.36 seconds). The failure was the existing graph assertion that all HTTP nodes retry once; it was updated to require zero retries on the three new review writes and preserve one retry on existing nodes. All original 416 tests remain; Step 8 tests explicitly cover their subgraph through independent agent validation, while new Step 9 tests cover the added continuation.

Final command: `.\.venv\Scripts\python.exe -m pytest -q --tb=short`. **447 passed**, one existing Starlette/httpx deprecation warning, **120.77 seconds**. This retains the original 416 cases and adds 31 Step 9 cases. Evidence: `data/verification/step9/pytest-final.txt`. No application tests were skipped or reported as live human approval.

After preserving the original canvas layout with the SDK's baseline merge, plan construction was bound directly to the typed normalized reconciliation output. The final targeted rerun, `.\.venv\Scripts\python.exe -m pytest tests/test_step9_flow.py tests/test_maestro_contract.py::test_emitted_graph_integrity -q --tb=short`, passed **9 tests** in **21.60 seconds**, with the same deprecation warning. The final canonical artifact also passed product validation with no warnings. All 49 pre-existing node IDs and the original layout remain present; the Flow now has 80 nodes. The full 447-case run preceded this equivalent input-binding/layout adjustment; the relevant nine tests ran afterward.

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

## Initial pre-redeployment Maestro acceptance status (superseded above)

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

## Working-form port follow-up
The standalone task100292180 completed Approve and its Flow completed. The same real614-character summary subsequently created diagnostic task100292253. Porting the working form into the original Flow passed validation and focused checks but four distinct configurations still returned170000. Original human approval remains blocked. Details and execution IDs: [working-form port](STEP9_WORKING_FORM_PORT.md).

## Saved comments-field mismatch fix
The saved Studio form declares reviewerCommentsOptional, while ApproveDisposition and RejectDisposition read form.comments. Updated both scripts and SDK schema to the actual saved field ID; older comments/reviewerComments task keys are read via Reflect.get and still checked as strings with the existing2000-character bound. Preserved the user's current schema ID, summary binding and canvas. Restored the agent node's missing errorHandlingEnabled=true flag because its existing error edge otherwise failed validation; agent prompts/sidecar were not changed.

Compile76nodes/79edges; candidate and installed product validation Valid. Focused pytest:8passed,1existing Starlette/httpx warning,22.90seconds. Selection: test_review_lowercase_comments_are_validated (Approve/Reject with old/current field names), test_review_graph_failures_and_tampering_fail_closed, TRF-1002 APPROVE/REJECT graph checks, test_emitted_graph_integrity. No live debug or cloud upload was performed for this editor-type-error fix. This does not claim the separate AppTasks400 issue is resolved.
