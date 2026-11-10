# Working Quick Form port to original Flow

The isolated task 100292180 completed with Approve; all five smoke-test nodes completed. The original TransferOperationsReview now uses the same simple Approve/Reject outcome shape, with a new schema identity and the title TransferIQ Operations Review. Its real validated investigationSummary binding, single-user Action Center assignment, string summary and optional comments remain. This is a controlled port, not a claim that the old outcome name was conclusively the cause.

The actual schema difference is Approve (id approve) replacing Approve Disposition (id approve-disposition). The outcome edge and the two decision scripts now validate the new actual label before recording the existing APPROVE/REJECT backend values. No dummy data entered the original Flow. The runtime profile remains Lite; financial rules, HTTP nodes, agent, IXP setting, node IDs and layout are unchanged.

Compile: 76 nodes, 79 edges, zero errors/warnings. Strict baseline merge passed. Candidate and installed product validation both returned Valid with no warnings. Resource refresh succeeded with the previously observed ImplicitConnection catalog advisory. Comparison with the saved original identified only TransferOperationsReview, ApproveDisposition and RejectDisposition as changed nodes; layout identical.

Focused regression: 50 passed, 1 existing Starlette/httpx deprecation warning, 33.81 seconds. Selection matches the 50-case command in STEP9_NOV9_DATA_DIAGNOSIS.md, using the updated Approve test-double label. These are local tests, not live human approvals. Full suite and missing Request Evidence/Escalate paths were not executed in this minimal-form port.

One real TRF-1002 debug launched with enableIXP=false. Live result is pending. A first PowerShell command failed to parse the unquoted @inputs path before executing the CLI; the corrected quoted command is the only launch.

The first port run 40dd3c39-dec9-4a1c-8ad5-8697e482a3f9 still faulted at TransferOperationsReview (170000). Plan preview returned 200 and its summary was a non-null string. Runtime asset comparison revealed that brownfield merge retained legacy node serialization: no explicit model and string output sources. The successful smoke-test asset has bpmn:UserTask / Actions.HITL model and structured source descriptors. Definitions were equal. This is an observed difference, not yet a proven root cause.

The node was then replaced in full with the SDK-emitted node using .flow-sdk/install-compiled-review-node.mjs, preserving its node ID, uniqueId, edges and layout. No hand-authored replacement node schema is used. Candidate product validation passed. Six focused checks passed (14.15 seconds; one existing deprecation warning). The first sandbox test attempt could not launch Python; the actual successful run used the approved escalation. A second live run tests this distinct serialization change.

The full-node replacement run 19540344-bc85-4033-86fc-462e51e4e944 also faulted with 170000. Its fetched runtime asset confirms the new model/structured output sources actually ran. Its task arguments contain a plain 614-character summary, so the binding is resolving. Neither serialization nor outcome naming alone fixes the failure.

A third distinct comparison removes the backed-up .maestro_automate marker and sets operate.json to Standard. Installed CLI source confirms the marker determines the effective debug package profile. Previous Standard comparison evidence does not independently record the packaged profile, and used the older node. This comparison retains the rebuilt node and real data; no identical configuration was relaunched.

Verified Standard+rebuilt-node run 326c848c-da52-4da2-98c9-d6bce892edd1 also failed170000. Profile alone is not the fix. Exact 614-character real summary was then passed through the API-free smoke Flow: instance4c920a3f-d3f3-498d-9a4d-c775e77920d6 created real task100292253 (Pending). This rules out that summary content/length as the cause of task creation failure. The original dummy-data smoke source/artifact were restored locally after capturing this comparison. Task100292253 remains a diagnostic task, not a backend approval.

Independent production verification of the second port run returned200 from both verify and audit: PREVIEWED, null human outcome, positionsUnchanged=true, transferCompleted=false, NOT_VERIFIED. No review was recorded.

## Final observed result
The final same-Standard-profile comparison removed only the legacy node uniqueId: instance838b4186-7c1a-4167-9cad-4414ea5d22a1 still faulted at TransferOperationsReview with170000. No further equivalent launches were made. The original Lite profile and marker were restored; the canonical Flow retains the SDK-emitted Approve/Reject node and updated fail-closed decision scripts. Product validation passed after replacement. The original Flow is NOT live-fixed, and no original-flow human completion is claimed. Four distinct original configurations were tested, plus one API-free real-summary comparison. No rate-limit failure was observed in these debug results; no retries of identical failing configurations were launched.

Remaining blocker: task creation in the original execution context still returns generic AppTasks400/170000 without a field-level response. Summary data, outcome normalization, complete SDK serialization, effective Standard profile, and removal of legacy uniqueId were insufficient. Exact root cause is unconfirmed; do not label this a permission or platform defect. The next discriminating evidence is the task-service request/schema validation details for the latest incident, or a supported fresh-project comparison of the complete original graph.

Changed files: original .flow-sdk/TransferIQ_Reconciliation.flow.ts, scripts/record-review-input.js, compiled TransferIQ_Reconciliation.flow, new install-compiled-review-node.mjs, tests/test_step9_flow.py (Approve label), and verification/status documentation. All original node IDs, edges except the renamed approval port, and layout remain. No financial rules or IXP settings changed.

Final six-test rerun after removing legacy uniqueId: 6 passed, one existing Starlette/httpx warning, 13.96seconds. This follows the initial50passed and intermediate6passed; these counts are overlapping executions, not56unique tests. Full suite was not run.
