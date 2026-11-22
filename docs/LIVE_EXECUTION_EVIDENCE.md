# TransferIQ AI live execution evidence

Audit date: **2026-11-19**. This file separates live production/UiPath evidence from automated tests and historical superseded runs. No new business workflow was started for this audit.

## Evidence rules

- **LIVE VERIFIED** means a production HTTP response, a UiPath tenant record, an Action Center task, or a retained real execution trace was inspected.
- **TEST VERIFIED** means current source was executed using isolated local fixtures or explicit test doubles.
- **NOT VERIFIED** means no trustworthy evidence was found for the requested live layer.
- A UiPath instance with runtime status `Completed` is not automatically a successful business result. The workflow outcome, verification response and audit ledger must agree.

## Current production and deployment reads

These were bounded GET/read operations. No automatic retry loop and no state-changing operation was used.

| Check | Result on 2026-11-19 |
|---|---|
| `GET /health` | HTTP 200; `status=ok`, `database=ok` |
| `GET /openapi.json` | HTTP 200; 51 paths |
| Local vs production OpenAPI | 51 vs 51; no missing or extra paths; both version 0.4.0 |
| `GET /portal` | HTTP 200, HTML |
| Production JavaScript asset | HTTP 200; `index-C0vY8r6s.js`, 394,523 bytes |
| Local/production JavaScript parity | Same filename and SHA-256 `7F5FE09A9B306F7E56186E679BB3FEE685C5CF1FE3DB2854445F934A1D36102D` |
| `GET /api/demo/transfers` | HTTP 200; five items |
| `GET /api/portal/session` without cookie | HTTP 200; enabled, unauthorized as designed |
| UiPath solution package | `TransferIQ-AI` 1.1.1, Active |
| UiPath deployment | Version 1.1.1, operation Successful, activation Active, `DemoFolder` |

The Step 11 approval and rejection records created on 2026-11-13 still returned HTTP 200 on 2026-11-19. This is direct evidence that those durable records remained available; it is not a controlled Render restart experiment. Restart persistence is separately covered by the automated suite.

## Current Step 11 approval

| Item | Verified value |
|---|---|
| Portal correlation | `PEX-f260efcbaaf04b52ab97bb693da1f922` |
| Flow instance | `de4d8ce5-076f-4ee0-90b0-3058514257d0` |
| Package/runtime | 1.1.1, Lite, IntegrationTrigger |
| Instance result | Completed, no incident returned by current instance read |
| Document retrieval job | `RetrieveCorporateActionDocument` completed |
| Agent job | `2b79ee78-c174-4311-92ba-826348a6291c`, completed |
| Real file-analysis evidence | Agent log created the `Analyze Files` internal tool and the real PDF attachment download returned HTTP 200 |
| Human task | 100314822, QuickFormTask, Completed, action Approve |
| Disposition/verification/audit nodes | `ExecuteDemoDisposition`, `VerifyDemoDisposition`, and `ReadReviewAudit` completed |
| Demo run | `DEMO-2c8c963b60b047efbbf993fbbb4d6a4f` |
| Plan | `PLAN-e8981354-39c2-42c8-af60-6586852fda8f`, EXECUTED |
| Production verify GET | HTTP 200; `VERIFIED_DEMO_STATE`, `REVIEWED_WITH_OPEN_EXCEPTIONS` |
| Audit GET | HTTP 200; 3 events |
| Financial result | `positionsUnchanged=true`, `transferCompleted=false`, `correctionsApplied=0` |

Analyze Files extracted SEC-103, `STOCK_SPLIT`, ratio 2:1, effective date 2026-08-10, notice date 2026-08-15, and evidence reference CA-2026-081. The agent's extraction was not trusted as authorization. The deterministic Flow validator compared it with the independent corporate-action API and promoted it to `VERIFIED`. SEC-104 remained unresolved at expected 120 versus receiving staging 100, difference `-20`.

## Current Step 11 rejection

| Item | Verified value |
|---|---|
| Portal correlation | `PEX-6cff39d5bba245f386157c2c76263229` |
| Flow instance | `9ce7b7cd-1086-4db4-9590-a9fee5a04ca3` |
| Package/runtime | 1.1.1, Lite, IntegrationTrigger |
| Instance result | Completed, no incident returned by current instance read |
| Human task | 100315016, QuickFormTask, Completed, action Reject |
| Demo run | `DEMO-ac0ef880d3d0475fb3e56f0dcfe9ed97` |
| Plan | `PLAN-e6251613-02d9-487e-a0f8-4cfcc30a1e75`, REJECTED |
| Production verify GET | HTTP 200; `VERIFIED_DEMO_STATE`, `REVIEW_REJECTED` |
| Audit | `PLAN_PREVIEWED`, `DEMO_REVIEW_RECORDED`, `DEMO_DISPOSITION_REJECTED` |
| Financial result | `positionsUnchanged=true`, `transferCompleted=false`; SEC-104 remains `-20` |

This is an actual human-completed rejection, not a simulated outcome. The reviewer identity remains the documented demo reference and must not be represented as production financial authorization.

## Current CLEAN control

| Item | Verified value |
|---|---|
| Portal correlation | `PEX-3a66c61996514c55bafbae3517f8ef56` |
| Flow instance | `ab6e29d9-1be6-40f2-a236-108c2b721d41` |
| Package | 1.1.1 |
| Result | Completed / CLEAN |
| Reconciliation | Seven direct matches, zero differences and zero exceptions |
| Nodes intentionally skipped | Document retrieval, Autonomous Agent, resolution-plan preview and Quick Form |

The CLEAN path proves that the workflow does not invoke expensive AI/document/human steps unnecessarily.

## Requested acceptance matrix

| Requested case | Evidence status | Best evidence | Limitation / next bounded test |
|---|---|---|---|
| TRF-1001 CLEAN | LIVE VERIFIED | 1.1.1 PEX and instance above | None |
| TRF-1002 approval | LIVE VERIFIED | 1.1.1 instance, Analyze Files evidence, task 100314822, plan/audit | None |
| TRF-1002 rejection | LIVE VERIFIED | 1.1.1 instance, task 100315016, rejected plan/audit | None |
| TRF-1003 identifier change | TEST VERIFIED | Deterministic mapping tests and catalog fixture | No retained current 1.1.1 portal run |
| TRF-1004 missing basis | TEST VERIFIED | Backend, resolution and Flow tests | No actual completed 1.1.1 Quick Form |
| TRF-1005 unsupported correction | PARTIAL LIVE | Older real reconciliation trace plus current tests | No current 1.1.1 agent/HITL run |
| API failure | LIVE + TEST VERIFIED | Real 429 Flow traces; bounded failure-path tests | Current portal error presentation was not re-executed live |
| Agent failure | LIVE VERIFIED | 1.1.0 instance `7864b5c0-f881-4bd1-91fa-197a0f800733` failed safely before review/write | Failure was fixed in 1.1.1 and retained as negative evidence |
| Invalid transfer ID | PARTIAL LIVE | Production direct 422 and tests | No current Maestro trace with final 422 response |
| Duplicate workflow trigger | TEST VERIFIED | Idempotency, conflict and no-duplicate-start tests | No live same-key replay capture |
| Portal completion tracking | LIVE/CONTRACT VERIFIED | Completed PEX correlations, production persisted plan/audit; deployed asset matches tested build | Authenticated status response was not reread during this audit because no operator credential was exposed |

## Historical evidence that remains useful

- Step 5 real cloud runs proved TRF-1001, TRF-1002 and TRF-1005 reconciliation routing. Those traces predate the current agent/document/HITL graph.
- Step 8 proved the real Autonomous Agent and independent supplemental-reference API while IXP was disabled.
- Step 9 proved manually completed approval/rejection and the corrected Quick Form continuation before portal/document automation.
- Step 10B proved portal webhook correlation and found/fixed the null reviewer reference.
- Step 11 supersedes those increments for the main TRF-1002 approval/rejection and TRF-1001 CLEAN acceptance.

Historical pass counts are not used as the current regression result. The fresh audit results are **478 backend tests passed**, **18 frontend tests passed**, successful frontend build, canonical Flow `Valid`, API Workflow `Valid`, and solution dry-run pack `Valid`.

## Evidence not claimed

- No IXP extraction ran in the Step 11 acceptance tests.
- No real ACATS transaction, trade, settlement, custody mutation or transfer completion occurred.
- No new Maestro business run was started for this audit.
- No current live TRF-1004 human review, current TRF-1005 human review, native Maestro evaluation run, or current in-Maestro invalid-ID 422 is claimed.
- The log query used to confirm Analyze Files was kept out of this document because runtime attachment URLs can be signed. Only the sanitized fact of tool creation and successful file download is reported.

