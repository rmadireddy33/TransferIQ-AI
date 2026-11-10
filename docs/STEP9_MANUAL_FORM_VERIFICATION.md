# Step 9 — manual form continuation verification

## Changes and preserved behavior

The user replaced the failing TransferOperationsReview node with Studio-created `quickForm1`, schema `cd4c3441-286c-4e58-90a2-c21beffaf6dc`. Run #8 (`bc52a9fe-883a-4cfd-b619-7b9fa341be0f`) and task `100292432` prove real task creation and Approve completion. That run then failed in ApproveDisposition and returned REVIEW_FAILED through an error-report branch; overall Completed did not mean review success.

The saved Approve script read the summary variable's `.output`, and Reject referenced the removed TransferOperationsReview. Both now read `$vars.quickForm1.output`, require the actual matching Action, and validate optional comments (including the saved field ID and prior aliases) as bounded strings. The backend proposal is still taken only from ValidateResolutionPlan; edits to the displayed inOut summary cannot change its plan version, hash, evidence or dispositions. Reject's saved `End` action was changed to `Continue` so its existing branch records rejection and produces an audit report.

Preserved the manual form's node ID, uniqueId, schema ID/type, field definitions, summary binding, output metadata, recipient/delivery settings, all other node IDs and canvas layout. Rebased SDK source from the current canvas, using the actual node/manifest JSON because the typed HITL factory cannot retain every saved field property. Changed only the form's Reject action and the two decision scripts in the compiled graph. No old form was reintroduced. The SDK wiring was corrected during compilation before installation; no failed candidate was executed.

The agent sidecar had lost its seven required output fields. Restored the existing authored required schema and explicit boolean constraint without changing current prompts. Financial reconciliation, source/staging positions, private/public API policy, IXP default and demo authorization semantics are unchanged. Review identity remains UNVERIFIED_DEMO_REFERENCE; this is not production financial authorization.

## Executed checks

- Initial focused suite: 57 passed, 1 failed because the agent output schema lacked `required`.
- After correction: `.\.venv\Scripts\python.exe -m pytest -q --tb=short`: **460 passed**, one existing Starlette/httpx deprecation warning, **135.52 seconds**. Tests include explicit human/agent doubles; they are not live human evidence.
- Current two-outcome graph tests replace the historical four-outcome graph assumption. Backend outcome tests remain; unsupported form outcomes are explicitly rejected. Added current comment-key and edited-summary coverage.
- Compile: **76 nodes, 79 edges**, zero compile errors/warnings in the final candidate. Node emitted its experimental TypeScript warning.
- Candidate and installed product Flow validation: **Valid**, no warnings.
- Resource refresh succeeded with the previously known ImplicitConnection catalog advisory. Actual manual-auth HTTP calls succeeded.

## Actual approval and CLEAN runs

| Case | Instance | Actual result |
|---|---|---|
| TRF-1002 Approve | `eab7e4a9-63a1-4c87-8806-d063a3f4bba0` | Completed through ReviewReport, VERIFIED_DEMO_STATE, REVIEWED_WITH_OPEN_EXCEPTIONS |
| TRF-1002 Reject | `93f9bd5d-4785-4ab0-b741-eac941da75b8` | Completed through ReviewReport, VERIFIED_DEMO_STATE, REVIEW_REJECTED |
| TRF-1001 | `2798bffb-42c9-4cbb-bef6-59b927fbcfa5` | Completed / CLEAN, IXP disabled |

Task **100292506** was completed manually by the user with Approve. Runtime comments were `approved`; the same value was passed to the backend. CreateDemoRun returned **201**, reconciliation **201**, preview **200**, record decision **200**, execute permitted demo dispositions **200**, verification **200**, audit **200**. No mocked human result was used.

Approval demo run `DEMO-b1090c03c8a3440c938afb5176e2ad8d`; plan `PLAN-c4246d50-0ad8-49ab-a6ae-b4a18dddff4b`. Independent production GETs for verify and audit both returned **200**. SEC-103 remains explained by verified CA-2026-081; SEC-104 remains UNRESOLVED with difference -20. positionsUnchanged=true, transferCompleted=false. Audit contains PLAN_PREVIEWED, DEMO_REVIEW_RECORDED and DEMO_DISPOSITION_EXECUTED.

Rejection is also live-verified: task **100292524** was manually completed with Reject. Instance `93f9bd5d-4785-4ab0-b741-eac941da75b8` completed through RejectDisposition, RecordReviewDecision and ReviewReport. All four review/execute/verify/audit HTTP nodes returned **200**. Independent verify/audit GETs returned **200** for demo `DEMO-74368cf1879743349d62003f8e464435`, plan `PLAN-aa81b92e-7528-42aa-90ff-8023f1d79774`. Plan status REJECTED; SEC-104 remains UNRESOLVED at -20; positionsUnchanged=true; transferCompleted=false. Audit events: PLAN_PREVIEWED, DEMO_REVIEW_RECORDED, DEMO_DISPOSITION_REJECTED. TRF-1004/TRF-1005 are covered locally but have not been run through live human completion in this follow-up. The historical 400 root cause is not proven; the successful manually created form is preserved.

Evidence: ignored `data/verification/step9/manual-form-review/` and sanitized `.local/investigations/raw/manual-*` under the original solution. Runtime review capabilities were redacted. Keep future changes in the SDK baseline-merge workflow; do not run the retired install-compiled-review-node helper or replace the user-created node with the old schema.

## Remaining scope

No blocker remains for the current Approve/Reject TRF-1002 paths or the CLEAN control. TRF-1004/TRF-1005 live human-review cases were not executed in this follow-up. Request Evidence/Escalate are not current form buttons; the backend retains its tests for those outcomes. IXP is still disabled by default and its separate model setup remains outside this change. No financial rule or quantity adjustment was introduced.

Files updated: canonical Flow and rebased .flow-sdk source; manual-review-node.json and manual-review-manifest.json preserve the actual saved node; scripts/record-review-input.js adapts its outputs; existing agent.json required output schema; tests/test_step9_flow.py and tests/test_step8_agent.py align with the current form; README, architecture, project plan and Step 9 evidence documents. The old installer helper targets the removed node and must not be used.
