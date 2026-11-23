# TransferIQ AI feature completeness matrix

Audit date: **2026-11-19**  
Native evaluation update: **2026-11-22**  
Scope: current source, deployed Render service, active UiPath solution 1.1.1, retained execution evidence, and fresh automated verification.

## Status model and completion calculation

| Code | Meaning | Completion credit |
|---|---|---:|
| A | Complete and verified in the appropriate live or executable layer | 1.0 |
| B | Implemented and test-verified, but the requested live acceptance evidence is incomplete | 0.5 |
| C | Incomplete, placeholder, or not submission-ready | 0.0 |
| D | Blocked by UiPath platform/tenant availability; an accepted alternative may exist | Excluded |
| E | Optional enhancement, not required for the current solution | Excluded |

The required-feature denominator is the 50 numbered rows below. After Flow-source
remediation, documentation reconciliation, and the bounded native-evaluation
run there are **43 A**, **6 B**, and **1 C** rows. Completion is therefore
`(43 + 6 x 0.5) / 50 = 92%`.

## Required features

| # | Feature | Status | Evidence source | Fresh or actual result | Remaining work | Priority |
|---:|---|:---:|---|---|---|:---:|
| 1 | Five fictional transfer scenarios | A | `backend/database/seed.py`, `seed_reconciliation.py` | Covered by 478-pass suite and production catalog returns 5 items | None | - |
| 2 | Transfer records and lifecycle | A | `backend/models/entities.py`, API tests | Protected private APIs and isolated public-run reads pass | None | - |
| 3 | Immutable delivering positions | A | models, DB triggers/migrations, reconciliation tests | Mutation and before/after invariants pass | None | - |
| 4 | Receiving transfer staging positions | A | models and reconciliation service | Kept distinct from settled custody; tests pass | None | - |
| 5 | Security master | A | seed and route tests | Seven TRF-1002 securities returned in scoped evidence | None | - |
| 6 | Corporate-action reference data | A | `CorporateAction`, `/corporate-actions` | CA-2026-081 verified and used independently | None | - |
| 7 | Security identifier mapping | A | mapping model/rules/tests | TRF-1003 is evidence-explained in deterministic tests | None | - |
| 8 | Cost-basis records and unknown handling | A | basis model/rules/tests | TRF-1004 reports one basis issue; unknown is not zero | None | - |
| 9 | Decimal deterministic reconciliation | A | `backend/services/reconciliation*.py` | Scenario counts and edge cases pass | None | - |
| 10 | Exception classification | A | reconciliation rules/tests | Split timing, quantity mismatch, mapping, basis and unsupported cases pass | None | - |
| 11 | Duplicate/idempotency handling | A | demo-run and resolution tests | Same-key replay/conflict and duplicate execution assertions pass | None | - |
| 12 | Financial immutability | A | DB constraints, service policy, verification APIs | Live approval/rejection both report `positionsUnchanged=true`, `transferCompleted=false` | None | - |
| 13 | Private PDF storage and integrity | A | document service/tests | Type, size, path, hash and private-download checks pass | None | - |
| 14 | Anonymous run isolation | A | `DemoRuns`, public endpoint tests | Per-run SQLite/PDF scope, TTL, quota and restart tests pass | None | - |
| 15 | Private API authentication | A | API dependency and security tests | Private GET/write routes require `X-API-Key` | None | - |
| 16 | Manual Trigger | A | canonical `.flow` | Node exists and prior real manual runs completed | None | - |
| 17 | Portal HTTP Webhook trigger | A | canonical `.flow`, live instances | Integration-triggered approval/rejection/CLEAN runs completed | None | - |
| 18 | Multi-step API orchestration | A | 14 HTTP nodes in canonical Flow | Live element trace shows discrete calls, not one monolithic backend call | None | - |
| 19 | Decision routing and fail-closed terminals | A | Flow decisions/scripts/tests | CLEAN, investigation, review and controlled failure branches are tested | None | - |
| 20 | Real Autonomous Agent node | A | canonical Flow and `agent.json` | Deployed agent jobs completed in real runs | None | - |
| 21 | Structured agent output validation | A | `validate-investigation.js`, agent schema/tests | Invalid actions/evidence/output are rejected independently | None | - |
| 22 | Real Analyze Files PDF analysis | A | built-in tool resource and live agent trace | Tool resource created; real attachment download returned 200; extracted split fields validated | None | - |
| 23 | Automated PDF retrieval API Workflow | A | `TransferIQ_Document_Retrieval/Workflow.json` | API Workflow validates/builds; live no-upload run completed | None | - |
| 24 | Honest API-only fallback | A | preparation script and tests | Missing/unavailable document stays `API_ONLY`; no extraction success is fabricated | None | - |
| 25 | Real Quick Form | A | `quickForm1`, task service | Single-user task created and completed in Action Center | None | - |
| 26 | Approve continuation | A | task 100314822, instance and backend plan | Plan EXECUTED; audit has three required events | None | - |
| 27 | Reject continuation | A | task 100315016, instance and backend plan | Plan REJECTED; no disposition applied | None | - |
| 28 | Request-evidence/escalation form outcomes | C | canonical Quick Form | Current form exposes only Approve and Reject | Add only if claimed in the submission; otherwise explicitly state out of scope | P2 |
| 29 | Append-only review audit | A | resolution service, SQL protections, live audit | Approval audit returns 3 events; immutability tests pass | None | - |
| 30 | Independent final verification | A | `/verify`, Flow verification node | Approval and rejection both return `VERIFIED_DEMO_STATE` | None | - |
| 31 | Portal session and CSRF security | A | `backend/api/portal.py`, `tests/test_step10b_portal.py`, `frontend/src/api.test.ts` | Signed HttpOnly/SameSite cookie; valid token and idempotent replay pass; missing/incorrect/expired/unauthenticated requests fail before persistence or webhook dispatch; read-only GET and independently authenticated M2M exemptions pass | Deploy the local correction before claiming production enforcement | P1 |
| 32 | Persisted portal lifecycle, history and bounded polling | A | portal registry, FastAPI/React tests | Operator-scoped global/transfer filtering, pagination, nullable historical fields, PEX reopen/return, status persistence, refresh, timeout and 60-poll bound pass | Deploy latest portal candidate and recheck asset parity | P1 |
| 33 | Workflow-complete vs transfer-complete distinction | A | portal UI and live verify response | UI explicitly says workflow completed while shortage remains unresolved | None | - |
| 34 | Render source/API parity | A | fresh OpenAPI and asset comparison | 51/51 paths match; JS name, length and SHA-256 match local build | None | - |
| 35 | Active UiPath solution deployment | A | tenant package/deployment reads | `TransferIQ-AI` 1.1.1 is Active/Successful | None | - |
| 36 | Reproducible authored Flow source | A | `.flow-sdk` source, pinned package/lockfile, binding template, comparison script, [reproduction procedure](MAESTRO_SOURCE_REPRODUCIBILITY.md) | Clean-directory source check 0 errors/0 warnings; compile 81 nodes/86 edges; pinned CLI 1.205.0 product validation `Valid`; exact node-ID and edge-tuple comparison passed | Target tenants must supply their own ignored bindings; CLI 1.206.0 has a documented dynamic Quick Form validator regression | - |
| 37 | Complete backend regression suite | A | fresh pytest run | **484 passed**, 0 failed, 0 skipped, 1 warning, 262.15s | None | - |
| 38 | Frontend tests and production build | A | fresh Vitest/TypeScript/Vite | **26 passed** across 2 files, 0 failed; production build successful (2,162 modules) | None | - |
| 39 | Native Maestro evaluation runs | B | `evals/`, [native evaluation report](MAESTRO_EVALUATION_REPORT.md) | Ten logical cases created; native TRF-1001 Flow run `816ba84e-ebbf-34a0-9342-e8df51d775cd` passed at 1.0; inline-Agent node run failed before agent output because its upstream file expression is unavailable in node scope | Establish a supported isolated Agent/file harness before claiming Agent evaluation completion | P1 |
| 40 | Judge reproduction material | A | current root docs, API inventory, deployment and judge guides | Current architecture, pinned CLI, bindings, reviewer assignment, and versioned historical evidence are consolidated | A second-tenant rehearsal remains a separate portability limitation | - |
| 41 | TRF-1001 current CLEAN live control | A | PEX-3a66..., instance ab6e29d9... | 1.1.1 completed CLEAN and skipped document/agent/form nodes | None | - |
| 42 | TRF-1002 current approval live path | A | PEX-f260..., instance de4d8ce5... | Analyze Files, approval, execution, verification and audit completed | None | - |
| 43 | TRF-1002 current rejection live path | A | PEX-6cff..., instance 9ce7b7cd... | Analyze Files, rejection, verification and audit completed | None | - |
| 44 | TRF-1003 current deployed-path run | B | deterministic tests only | Mapping scenario is implemented; no retained 1.1.1 portal trace | One bounded run only if it adds judging value | P1 |
| 45 | TRF-1004 current human-review run | B | local backend/Flow tests | Missing-basis behavior is tested; no actual completed 1.1.1 task | One bounded approval or rejection test | P1 |
| 46 | TRF-1005 current human-review run | B | old Step 5 live trace and current tests | Reconciliation live evidence exists, but not current agent/document/HITL path | One bounded 1.1.1 test | P1 |
| 47 | API failure safe handling | A | real 429 traces plus failure tests | Real 429 stopped safely; 401/403/404/422/503/network paths are tested | Optional current portal screenshot/trace | P2 |
| 48 | Agent startup failure safe handling | A | PEX-13e..., instance 7864b5c0... | Real 1.1.0 input-schema failure stopped before review or write | None; retained as negative evidence | - |
| 49 | Invalid transfer ID through current Maestro | B | production direct 422 and tests | Direct API contract verified; in-Maestro 422 is not captured | One bounded Manual Trigger negative run | P1 |
| 50 | Duplicate portal trigger live acceptance | B | backend/frontend idempotency tests | No duplicate live trigger trace retained | Demonstrate same idempotency key once without launching a second run | P1 |

## Platform-blocked and optional items

| Feature | Status | Evidence | Treatment |
|---|:---:|---|---|
| IXP document node inside the Flow | D | Community tenant limitation recorded in Step 11 | Not a completeness defect because the supported built-in Analyze Files route is real and verified; do not claim IXP ran. |
| Production-grade reviewer identity/entitlements | E | Current service labels reviewer identity `UNVERIFIED_DEMO_REFERENCE` | Required before any real brokerage write, but outside this fictional, non-transactional challenge demo. |
| Real ACATS/trading/settlement | E | Explicitly absent in architecture and APIs | Must remain absent; the solution is synthetic and read-only with respect to custody. |

