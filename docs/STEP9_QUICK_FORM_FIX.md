# Step 9 Quick Form comparison and incremental fix

## Actual working reference

The user-completed **Quick Approval** task `100265305` belongs to Flow **New Flow**, Flow ID `be7ec06a-9f75-42b8-b9bd-f2ceb59d3649`, instance `dc22b7a5-ebc8-4ce8-ba21-766351d466b5`. Task state is Completed, action Submit, completed at `2026-11-06T06:00:05.6770457Z`. Supported task/instance reads retrieved its actual runtime definition. The user then supplied the Studio Web URL and `uip solution download` retrieved solution `5a574b7c-2eb8-4760-2409-08df39afdaa6`, project `2f2476a1-327b-4a41-a286-fc006bb68116`. Its saved 1.9 manifest exactly matches the recovered runtime manifest. The reference form was read, not modified or copied wholesale into TransferIQ.

## Meaningful differences

| Property | Working reference | Original TransferIQ failure |
|---|---|---|
| Node | `uipath.human-in-the-loop.quick-form` | Same family |
| Definition version | **1.9** | **1.0**, emitted by installed typed SDK factory |
| Title | `inputs.schema.title = Quick Approval` | `inputs.title` JavaScript expression; no schema title |
| Assignment | Type user, literal signed-in email, displayName present | Type user, `=js:` reference to trigger input; displayName absent |
| User/folder | Verified signed-in user, folder 519923 / `ff1e40d3-3531-41ec-bb0c-270f86f7043d` | Same user and debug folder |
| Delivery | ActionCenter plus Email/Slack/teams defaults | ActionCenter only |
| Decision schema setting | `enableDecisionSchema=false` | Not emitted |
| Fields | One optional output string, `comments` | Twelve readonly strings and two optional output strings |
| Outcomes | Submit / Continue | Approve Disposition, Request Evidence, Escalate, Reject / Continue |
| Readonly runtime bindings | None | Bound to validated plan output |
| Output property metadata | `fieldId` present | No explicit fieldId |

The fresh CLI registry returns version 1.7; it does not expose the working saved 1.9 definition through `registry get`. The 1.9 manifest was therefore retained from the actual working instance asset. CLI DTO property-name casing was normalized to the Flow manifest's camelCase; property values/defaults were not invented. The installed typed `hitl()` factory cannot represent the working `schema.title` contract/version. The builder's documented `rawNode` path carries the actual manifest and still compiles the real Quick Form node. This is not a mock or replacement Script.

## Failed runtime input inspection

Instance `0f22d0f0-6d7e-4175-92e0-186bfdb5707b` reached TransferOperationsReview after real agent and plan validation. All twelve supplied readonly values were **strings**, with no null values: transferId 8 characters, client reference 7, exception count 1, investigation summary 567, corporate-action facts 287, shortage facts 302, evidence text 15, dispositions text 318, planId 41, planHash 64, risk 6, demo notice 136. The structured evidence/dispositions were JSON text, not raw objects/arrays. These measurements do not establish a provider size limit, but reveal no obvious null/type/large-payload issue. The summary/evidence correctly retain SEC-103's verified split and SEC-104's unresolved 20-share shortage. Runtime credentials/capabilities are excluded from this report.

The task error was HTTP 400 / 170000 with no field-level response. Email and GUID trigger inputs both failed under the original expression-based configuration. That did not prove either user identifier itself was invalid; the working task now proves this email and folder can create tasks.

## Minimal original-Flow candidate

Only the retained `TransferOperationsReview` node was changed: working 1.9 definition, schema title, literal single-user assignment from ignored local configuration, one readonly summary string, one optional comments string, and Approve Disposition/Reject. The existing approve/reject scripts and backend mappings remain unchanged. Request Evidence and Escalate's four nodes/six edges are temporarily absent during this explicitly requested minimal test; the complete original source/artifact/scripts are backed up for incremental restoration.

All other retained node IDs and layout are preserved, including the agent, reconciliation, IXP configuration and APIs. The agent sidecar hash is unchanged. The source reads `quickFormReviewerEmail` from ignored `.flow-sdk/runtime.local.json`; it does not hardcode tenant identity. As with the working Studio configuration, the compiled local artifact contains its configured assignee.

Compile: **76 nodes / 79 edges**, zero errors/warnings. Product validation: **Success / Valid**, no warnings. Evidence is under ignored `data/verification/step9/quickform-fix/`, including the scope diff and original backup. The first minimal run `6b88649a-8b1c-4711-a92e-503334429537` still failed with 400/170000. A second candidate used lowercase summary/comments IDs and a fresh TransferIQ schema ID; run `72bf9d64-545e-4b53-83fe-467ed8120b58` also failed. One controlled Standard-profile comparison `03919b29-36b3-40eb-96ef-0f6997c0ba0c` had the same failure; the local original Lite profile was restored. None created an observed human task. No identical configuration was retried to inspect results.

Root cause remains a configuration-contract hypothesis until the real test succeeds. Because the minimal candidate changes several related schema/assignment details and reduces fields, a successful minimal test alone cannot identify one property as the sole cause. Additional fields/outcomes will be restored only after the minimal form works.

The November 9 user run exposed a separate null agent-output flag before the form. That contract was corrected and verified in real instance `de7e148a-2147-426f-a6ae-f3a8aad544e7`: agent validation and preview succeeded, then Quick Form still returned 400/170000. Backend verify/audit returned 200 with no decision/dispositions, unchanged positions and the unresolved -20 shortage. See [the current diagnosis, tests and exact evidence](STEP9_NOV9_DATA_DIAGNOSIS.md). The task-service response remains null and does not identify a rejected property; neither permissions nor a platform defect has been proven.
