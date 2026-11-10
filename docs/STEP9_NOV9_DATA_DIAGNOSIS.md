# November 9, 2026 — TRF-1002 runtime investigation

The recent TRF-1002 run did not reach the Human Quick Form. Its HTTP requests succeeded, but independent agent-output validation safely ended the business path with `INVESTIGATION_REVIEW_REQUIRED`. Maestro's terminal `Completed` status does not mean human review succeeded.

## Observed executions

| Instance | Input | Observed result |
|---|---|---|
| `32f6d8e4-39b3-430c-b50e-2fe7945d1bda` | TRF-1002 | CreateDemoRun 201; transfer/source/staging/reference GETs 200; reconciliation 201. Agent output rejected with `INVALID_REPORT_CONTRACT`; TransferOperationsReview never executed. |
| `a4cb8f7f-cb3e-42a1-a3f1-e40d4e692a93` | SEC-104 | CreateDemoRun returned 429, then the error branch returned business outcome FAILED. No reconciliation or human task. The response body was not exposed, so the precise rate/quota source is unconfirmed. |

The first run started at `2026-11-10T02:03:07Z` (November 9 in the user's America/New_York timezone). Both instances belong to the actual TransferIQ_Reconciliation Flow, ID `fa7de741-ad8f-441f-8f3d-9bf96e5f3497`, in the previously verified debug folder. Their runtime assets and incidents were retrieved through supported UiPath commands. No new execution was launched to discover these facts.

## Proven rejection

The actual Agent run and Agent output trace spans both contain top-level `requiresHumanReview: null`. Each individual finding contains `requiresHumanReview: true`. The validator requires the top-level value to be exactly boolean true and therefore rejects the report. This is not a Flow-output mapping assumption: null is already present in the agent's own trace output.

The actual runtime output schema declares the property as boolean, but has no `required` array or true-only constraint. The prompt already requests true, which did not prevent this observed invalid answer. The correction must strengthen the emitted agent contract and retain rejection of missing/null/false values; it must not manufacture a successful agent answer or relax the validator.

TRF-1002's reconciliation data is consistent with its intended scenario: SEC-103 is explained by verified split evidence CA-2026-081; SEC-104 has 120 expected versus 100 receiving, difference -20, unresolved. Supplemental evidence was available (`missingEvidence=[]`). IXP was disabled. SEC-104 is a security identifier within the transfer, not a valid replacement for transferId.

## Evidence and limits

Ignored local evidence: `maestro/TransferIQ_Reconciliation/.local/investigations/raw/previous-latest-{variables,asset,incidents}.json`, `latest-{variables,asset,incidents}.json`, and `nov9-agent-trace.json`. Review capabilities are redacted from variable captures. The current cloud solution was downloaded under ignored `data/verification/step9/nov9-cloud/` before edits.

This rejection is distinct from the earlier Quick Form HTTP 400 / incident 170000. Correcting the agent output does not establish that task creation or manual completion works. Those require a subsequent real execution and observed task identity.

## Applied correction and verification

The correction candidate adds a required, boolean-true-only top-level `requiresHumanReview` to the actual agent output schema, reinforces that distinction in the prompt, and adds precise missing/null/non-true diagnostics without relaxing the validator. The reviewer input defaults to the configured Quick Form assignee from ignored local configuration. The user's observed run had an empty reviewer reference; that was not the cause of its earlier agent-validation stop, but would prevent subsequent plan construction.

The candidate uses the SDK's sidecar-based inline-agent representation and preserves the agent/source IDs, model, existing business edges and cloud canvas layout. A schema finalizer is necessary because the SDK's primitive `returns` declarations do not express required fields or enum constraints. The packaged candidate was inspected and retains all seven required output fields and the true-only constraint.

Application was initially blocked by an unexplained external writer: after copying the corrected files into the original project, the agent schema reverted from seven required fields to no required list within three seconds, without a UiPath CLI or pytest command running. Reversion was also seen during validation/testing, but those commands are not established as the cause. After the user closed the open sessions, both files remained stable, canonical product validation returned **Success / Valid**, and the schema retained all seven required fields. The exact writer was not identified.

One real post-fix TRF-1002 run was executed: **`de7e148a-2147-426f-a6ae-f3a8aad544e7`**. Inputs supplied only transferId and enableIXP=false. The configured reviewer default resolved correctly. Actual Agent run trace confirms the required schema and `enum:[true]` reached the runtime, and the agent returned **requiresHumanReview=true**. Independent validation returned **INVESTIGATION_COMPLETED**, validationErrors=[], missingEvidence=[]. Run creation returned **201**, plan preview **200**.

The run then reached the existing Quick Form and failed with **HTTP 400 / incident 170000**, Response=null. Incident ID `5f387248-51d5-41fa-947f-c2ce187516b4`; trace `de7e148a2147426fa6aef3a8aad544e7`. A folder-scoped task query found no matching task. Thus the agent-output issue is corrected and live-verified, but **Quick Form creation remains unresolved**. No human completion or disposition execution occurred. No equivalent retry was launched.

Independent production verification and audit GETs both returned **200** for run `DEMO-b9f9b0001b4341aab5390c2764036bff`, plan `PLAN-3b16f73d-7e89-4d1a-89d0-b2af278abb4a`: PREVIEWED, null humanReviewOutcome, zero dispositions, positionsUnchanged=true, transferCompleted=false; SEC-104 remains UNRESOLVED with difference -20. Audit contains only PLAN_PREVIEWED. The earlier 429 response body was unavailable; no repeated creation requests were launched to investigate it.

### Executed local checks

Compile: **76 nodes, 79 edges**, no compile warnings/errors. Product validation passed for the isolated candidate and then for the installed canonical Flow after the user closed sessions. All node IDs, edges, layout and cloud trigger identity are preserved. The agent's error-end node has SDK metadata changes only; its output expression and business behavior are unchanged.

Focused regression on the isolated candidate: **50 passed**, one existing Starlette/httpx warning, **22.30 seconds**. The same selection on the installed project after the overwrite stopped: **50 passed**, the same warning, **19.70 seconds**. These are local backend/graph tests with explicit agent/human test doubles, not human approvals.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_step8_agent.py 'tests/test_step9_flow.py::test_review_graph_against_real_backend_responses[TRF-1002-APPROVE]' 'tests/test_step9_flow.py::test_review_graph_against_real_backend_responses[TRF-1002-REJECT]' 'tests/test_step9_flow.py::test_review_graph_against_real_backend_responses[TRF-1004-APPROVE]' 'tests/test_step9_flow.py::test_review_graph_against_real_backend_responses[TRF-1005-APPROVE]' tests/test_step9_flow.py::test_review_lowercase_comments_are_validated tests/test_step9_flow.py::test_review_graph_failures_and_tampering_fail_closed tests/test_maestro_contract.py::test_emitted_graph_integrity -q --tb=short
```

An earlier canonical attempt had 49 passed/1 failed because the sidecar was overwritten. An initial broader selection had 49 passed/3 failed (the schema overwrite and two outcomes intentionally absent from the minimal canvas). The complete suite was **not** rerun; the original four-outcome form has not been restored or live-accepted. Evidence: ignored `data/verification/step9/nov9-agent-contract/`, including `pytest-installed.txt`, `regression-result.json`, `validate-installed.json`, live execution output and independent backend checks.

### Rebuilding without losing the contract

Keep the SDK brownfield sequence: capture the pristine compiled baseline before source edits; compile the edit to a staging directory; merge its delta into the saved cloud artifact; retain the edited agent sidecar beside the merged Flow; run `.flow-sdk/finalize-agent-contract.mjs <merged-flow-path>`; product-validate; then install the validated artifact and sidecar. The finalizer applies the authored `.flow-sdk/agent-output-schema.json` without supplying any runtime answer or default.

The existing `scripts/build-maestro.ps1` now invokes the schema finalizer after compilation, but its compile/format workflow does not replace this baseline-merge procedure. Do not format the merged brownfield canvas. Preserve the ignored reviewer configuration and run resource refresh before a real debug upload.
