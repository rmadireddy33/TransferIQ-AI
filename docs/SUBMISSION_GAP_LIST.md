# TransferIQ AI submission gap list

Audit date: **2026-11-19**. Documentation-reconciliation update:
**2026-11-22**. Final release gate: **2026-11-22**.

Current recommendation: **PASS WITH LIMITATIONS**. Full details and exact
commands are in [FINAL_RELEASE_VERIFICATION.md](FINAL_RELEASE_VERIFICATION.md).

## Closed during targeted remediation

### P0-1 - Make the authored Flow reproducible — CLOSED 2026-11-19

- **Original issue:** `uip maestro flow check .flow-sdk/TransferIQ_Reconciliation.flow.ts --source` reported 3 errors and 3 warnings. The errors concerned the preserved raw Quick Form outcome ports and a cross-port reference. Standalone compilation succeeded at 81 nodes/86 edges but reported 4 `CONNECTION_STUB` warnings because ignored `.flow-sdk/bindings.json` was absent. The installed canonical `.flow` validated and ran, so the defect was source/canonical reproducibility rather than production execution.
- **Why it matters:** Build quality is the challenge's largest criterion and tie-breaker. A judge should not need the owner's already-merged canonical artifact to obtain a runnable graph.
- **Implemented fix:** The source now uses typed HITL outcome routing, preserves `quickForm1`, both saved outcome IDs, the Autonomous Agent file binding and every canonical node/edge, and includes pinned tooling, an ignored-binding template/process, required agent-contract finalization and an automated semantic comparison. See [MAESTRO_SOURCE_REPRODUCIBILITY.md](MAESTRO_SOURCE_REPRODUCIBILITY.md).
- **Complexity:** Medium to high; 1-2 focused engineering days because the Quick Form is a brownfield node.
- **Verification:** Source check returned 0 errors/0 warnings; a clean-directory compile returned 81 nodes/86 edges; pinned UiPath CLI 1.205.0 returned `Success / Valid`; no node IDs or edge tuples differed; Quick Form and agent input contracts were semantically equivalent. No live path was rerun because nothing was deployed.

### P0-2 - Produce a clean, internally consistent submission package — CLOSED 2026-11-22

- **Original issue:** Root, deployment, and judge documents mixed earlier
  reconciliation-only and failed-form milestones with the current 1.1.1 state.
- **Implemented fix:** Reconciled README, architecture, project plan, Render and
  Railway guidance, API inventory, zero-credential boundaries, judge setup,
  tenant bindings, reviewer assignment, CLI compatibility, and environment
  comments. Older Step records are explicitly historical where needed.
- **Verification:** Local Markdown links, route names, file references, version
  assertions, and current-state contradiction searches are checked by the
  documentation validation procedure.
- **Separate limitation:** Source/package/deployment provenance is owner-managed
  in another folder and was not changed or asserted by this documentation task.

## P1 - important for scoring

### P1-0 - Reconcile the checked-in canonical resource binding — OPEN 2026-11-22

- **Evidence:** The pinned 1.205.0 source check is clean, source compilation
  produces 81 nodes/86 edges, the candidate validates `Success / Valid`, and
  semantic comparison reports no missing/extra node IDs or edge tuples. The
  checked-in canonical artifact has the same graph but standalone validation
  reports one error and two warnings because the
  `TransferIQ_Document_Retrieval` workflow-level `name` and `folderPath`
  binding rows are absent.
- **Impact:** Production 1.1.1 is operational and the solution dry-run is
  `Valid`, so this is not an observed production outage. It does invalidate the
  unqualified documentation claim that the checked-in canonical `.flow`
  validates standalone and can surprise a judge following that command.
- **Required fix:** With explicit approval, regenerate or narrowly repair only
  the canonical binding rows from the valid source-built candidate. Preserve
  every node ID, edge tuple, trigger, Agent input, Quick Form outcome, and
  resource reference. Repeat standalone validation, semantic comparison, API
  Workflow validation, and solution dry-run. Do not deploy as part of the fix.

### P1-0A - Enforce the documented CSRF header requirement — SOURCE CLOSED / DEPLOYMENT PENDING 2026-11-22

- **Evidence:** An isolated local TestClient probe used a signed session cookie,
  valid idempotency key, and webhook test double but omitted
  `X-CSRF-Token`; the start returned HTTP 201. The route header is optional and
  `_read_session` compares it only when supplied.
- **Root cause:** `_read_session` compared the session claim only when the
  optional request header was supplied, so omission selected no CSRF check.
- **Local correction:** Investigation start now invokes the existing session
  reader with `require_csrf=True`. Missing/incorrect headers return 403 before
  manager access, PEX persistence, or webhook dispatch. Read-only GETs and
  independently capability-authenticated machine callbacks remain exempt.
- **Verification:** Focused portal tests pass 15/15; complete backend tests pass
  484/484; frontend tests pass 26/26; production build succeeds. Negative tests
  assert zero database rows and zero webhook calls. Valid start and idempotent
  replay retain one webhook call.
- **Remaining action:** Deploy the reviewed source to Render without changing
  secrets or persistent data, then run one bounded missing-header check. Do not
  claim production enforcement until that returns 403 with no PEX/UiPath side
  effect.

### P1-1 - Complete native Agent evaluations — PARTIALLY CLOSED 2026-11-22

- **Completed:** Ten logical cases now exist. Native Flow run
  `816ba84e-ebbf-34a0-9342-e8df51d775cd` executed `TRF-1001` and scored 1.0
  on exact CLEAN outcome and clean-routing trajectory. It skipped the Agent,
  Analyze Files, document retrieval, review writes, and Quick Form.
- **Remaining blocker:** Node-scoped Agent run
  `cd725560-7c16-bf4a-6d16-47aed11d579b` executed three workloads, but each
  reached controlled `AgentFailed` before an agent job. Node scope did not run
  `ValidateInput`, while the preserved Agent node file binding evaluates
  `vars.ValidateInput.output.corporateActionPdf`. A separate Agent-native run
  failed with zero cases because this Agent is an inline Flow sidecar, not a
  standalone Agent project pushed to Studio Web.
- **Why it matters:** The passed CLEAN case is useful native evidence, but it
  does not measure Agent classification, grounding, structured output, or tool
  behavior.
- **Required fix:** Use a UiPath-supported isolated Agent/file evaluation
  harness that can supply the nullable upstream file input, or register an
  equivalently configured standalone evaluation Agent. Do not alter the
  production prompt/model or run full TRF-1002 batches that create human tasks.
- **Verification:** Agent workloads must actually produce structured output;
  deterministic fields must pass; the genuine file route must call Analyze
  Files exactly once; API-only routes must call it zero times. See
  [MAESTRO_EVALUATION_REPORT.md](MAESTRO_EVALUATION_REPORT.md).

### P1-2 - Close the remaining live acceptance gaps with a bounded plan

- **Exact issue:** No current 1.1.1 live evidence exists for TRF-1003, TRF-1004 human completion, TRF-1005 current agent/HITL path, current in-Maestro invalid-ID 422, or live duplicate webhook replay. Automated coverage is strong, but the requested live matrix is incomplete.
- **Why it matters:** These cases demonstrate completeness beyond the primary happy path.
- **Required fix:** Run only the minimum non-duplicative set: one TRF-1004 human outcome, one TRF-1005 opposite outcome if it adds evidence, one Manual Trigger invalid ID, and one same-idempotency replay that proves no second Flow instance. TRF-1003 is optional if the evaluation dataset covers it convincingly.
- **Complexity:** Low to medium; several bounded tests plus evidence capture.
- **Verification:** Record PEX/instance/task IDs, package 1.1.1 or later, terminal business outcome, audit, unchanged positions and incident count. Do not retry identical failing configurations.

### CLOSED AND DEPLOYED - P1-3 - Improve demo clarity without changing business logic

- **Resolution:** The sanitized PEX projection now persists the plan's document-evidence method. Both active investigation views distinguish `AGENT_ANALYZE_FILES`, `API_ONLY`, and document evidence unavailable; the legacy component and active-source encoding artifacts are removed; and a concise evidence-method panel explains the deterministic API validation boundary without exposing capabilities or file URLs.
- **Safety:** The portal remains read-only for decisions. No Flow, prompt, Quick Form, webhook, financial rule, or position was changed.
- **Complexity:** Medium; 0.5-1 day plus tests.
- **Verification:** Analyze Files, API-only, unavailable, and pre-migration plan-fallback fixtures render accurate labels; the six-stage status view and global/transfer-specific operator history remain backend-derived; 30 frontend tests and the production build pass; all 481 backend tests pass. Fresh SHA-256 checks show the deployed JavaScript and CSS are byte-identical to the local build. The owner visually reviewed seven persisted production investigations: one for TRF-1001 and six for TRF-1002.

### P1-4 - Rehearse tenant dependencies and portable assignment

- **Exact issue:** The import/bind/assign checklist is now documented, but a
  clean second-tenant rehearsal has not been retained.
- **Why it matters:** Public browsing is zero-credential, but running the full Flow in another tenant is not zero setup.
- **Required fix:** Execute the documented process in a second tenant without
  reusing owner identifiers or editing financial logic.
- **Complexity:** Low; documentation plus a clean-tenant rehearsal.
- **Verification:** A second tenant user can import, bind and validate without editing financial logic; every required tenant choice is called out before run.

## P2 - optional enhancements

### P2-1 - Decide whether Request Evidence and Escalate are in scope

- **Issue:** Backend outcomes exist, but the current Quick Form has only Approve and Reject.
- **Treatment:** Do not advertise the absent buttons. Add them only if the demo story needs them and only with new live acceptance.
- **Complexity:** Medium.
- **Verification:** New outcomes continue through decision persistence, verification and audit without changing positions.

### P2-2 - Add release provenance and observability

- **Issue:** Backend `/health` and OpenAPI expose application version 0.4.0 but no source SHA or Render deploy ID.
- **Treatment:** Optionally expose a non-secret build identifier and document coordinated SQLite/PDF backup/restore evidence.
- **Complexity:** Low to medium.
- **Verification:** Build identifier matches tagged source; it contains no secret or tenant credential.

### P2-3 - Add browser end-to-end checks

- **Issue:** React behavior is well unit-tested, but there is no checked-in Playwright acceptance suite for deployed navigation and refresh.
- **Treatment:** Add read-only browser tests for dashboard, tracking states, audit link, refresh, mobile layout and accessibility basics.
- **Complexity:** Medium.
- **Verification:** Tests run against a local isolated backend and optionally production read-only routes; they never start a workflow unless explicitly enabled.

## Top five competitiveness gaps

1. The checked-in canonical graph is 81/86-equivalent but lacks the two binding rows required for standalone validation.
2. The local CSRF correction is regression-green but has not yet been deployed and verified on Render.
3. Native CLEAN evaluation passes, but native inline-Agent evaluation is blocked before agent output.
4. Source-to-deployment provenance is maintained externally and a second-tenant binding rehearsal is not retained.
5. Current live evidence does not cover every requested secondary scenario/failure/replay case.

## Release interpretation

The deployed demo is functional, financially safe, regression green, and has
exact frontend asset parity, so the final competition recommendation is
**PASS WITH LIMITATIONS**. Both original P0 remediation items remain closed.
The canonical binding issue and pending production rollout of the locally fixed
CSRF check block an unqualified PASS but do not demonstrate a production outage
or financial-state failure. Agent-evaluation completion, external provenance, secondary live
coverage, a second-tenant rehearsal, and optional history-scroll accessibility
polish also remain. None justifies changing deterministic reconciliation or
custody data.

