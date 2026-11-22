# TransferIQ AI submission gap list

Audit date: **2026-11-19**. No fixes in this list were implemented during the audit.

## Closed during targeted remediation

### P0-1 - Make the authored Flow reproducible — CLOSED 2026-11-19

- **Original issue:** `uip maestro flow check .flow-sdk/TransferIQ_Reconciliation.flow.ts --source` reported 3 errors and 3 warnings. The errors concerned the preserved raw Quick Form outcome ports and a cross-port reference. Standalone compilation succeeded at 81 nodes/86 edges but reported 4 `CONNECTION_STUB` warnings because ignored `.flow-sdk/bindings.json` was absent. The installed canonical `.flow` validated and ran, so the defect was source/canonical reproducibility rather than production execution.
- **Why it matters:** Build quality is the challenge's largest criterion and tie-breaker. A judge should not need the owner's already-merged canonical artifact to obtain a runnable graph.
- **Implemented fix:** The source now uses typed HITL outcome routing, preserves `quickForm1`, both saved outcome IDs, the Autonomous Agent file binding and every canonical node/edge, and includes pinned tooling, an ignored-binding template/process, required agent-contract finalization and an automated semantic comparison. See [MAESTRO_SOURCE_REPRODUCIBILITY.md](MAESTRO_SOURCE_REPRODUCIBILITY.md).
- **Complexity:** Medium to high; 1-2 focused engineering days because the Quick Form is a brownfield node.
- **Verification:** Source check returned 0 errors/0 warnings; a clean-directory compile returned 81 nodes/86 edges; pinned UiPath CLI 1.205.0 returned `Success / Valid`; no node IDs or edge tuples differed; Quick Form and agent input contracts were semantically equivalent. No live path was rerun because nothing was deployed.

## P0 - must fix before submission

### P0-2 - Produce a clean, internally consistent submission package

- **Exact issue:** `README.md`, `ARCHITECTURE.md`, `PROJECT_PLAN.md`, `ZERO_CREDENTIAL_DEMO.md`, `JUDGING_ACCESS.md`, and some Step 5-10 documents still say that agents, Quick Forms, portal triggers or document analysis are future/unverified work. Several files also contain visible mojibake. The workspace has no Git repository metadata, so a source commit cannot be correlated with Render or package 1.1.1.
- **Why it matters:** Judges can easily conclude that the project is incomplete or cannot determine which statements are authoritative. The challenge form requires accessible solution files and a demonstrable build history with the coding agent.
- **Required fix:** Make the five audit files the authoritative entry point, update root status sections, mark older reports explicitly historical, correct encoding, initialize/use the intended source repository, tag the exact submitted revision, and record package/source traceability without committing secrets or runtime traces.
- **Complexity:** Medium; 0.5-1 day.
- **Verification:** Fresh clone/import follows `JUDGE_REPRODUCTION_GUIDE.md`; all root links resolve; search finds no current-tense claims that contradict Step 11; package metadata identifies the submitted revision; repository secret scan is clean.

## P1 - important for scoring

### P1-1 - Run native Maestro evaluations

- **Exact issue:** The Flow has evaluator definitions, but `evaluation-set.json` contains zero data points and there is no evaluation-run result.
- **Why it matters:** Official guidance explicitly asks entrants to test before shipping and recommends whole-workflow evaluations plus tool-call evaluators for agent behavior.
- **Required fix:** Capture real successful runs into a whole-flow dataset for CLEAN, approval-with-open-exception and rejection; add an agent dataset that checks structured fields and Analyze Files call count/arguments; add malformed/missing-document failure cases with simulations where a live human is unnecessary.
- **Complexity:** Medium; 0.5-1 day.
- **Verification:** Export evaluation run IDs and scores; deterministic fields use Exact Match/JSON similarity; Analyze Files is called exactly once only on the file route; all expected failure paths score correctly.

### P1-2 - Close the remaining live acceptance gaps with a bounded plan

- **Exact issue:** No current 1.1.1 live evidence exists for TRF-1003, TRF-1004 human completion, TRF-1005 current agent/HITL path, current in-Maestro invalid-ID 422, or live duplicate webhook replay. Automated coverage is strong, but the requested live matrix is incomplete.
- **Why it matters:** These cases demonstrate completeness beyond the primary happy path.
- **Required fix:** Run only the minimum non-duplicative set: one TRF-1004 human outcome, one TRF-1005 opposite outcome if it adds evidence, one Manual Trigger invalid ID, and one same-idempotency replay that proves no second Flow instance. TRF-1003 is optional if the evaluation dataset covers it convincingly.
- **Complexity:** Low to medium; several bounded tests plus evidence capture.
- **Verification:** Record PEX/instance/task IDs, package 1.1.1 or later, terminal business outcome, audit, unchanged positions and incident count. Do not retry identical failing configurations.

### P1-3 - Improve demo clarity without changing business logic

- **Exact issue:** The transfer Investigation tab hardcodes `NOT_PROCESSED_IXP_DISABLED` even when the Step 11 route used `AGENT_ANALYZE_FILES`; the durable public plan view exposes only the summary, not the full structured agent/document result. `LegacyInvestigationProgress` remains dead code. Some UI strings contain mojibake. These are not financial defects but weaken the demo.
- **Why it matters:** A judge may mistake “IXP disabled” for “no document analysis” and miss the strongest innovation. Dead/stale presentation code increases maintenance risk.
- **Required fix:** In a separately authorized UI polish change, label evidence mode accurately from persisted data, present the sanitized structured document-validation result, remove dead legacy component code, correct encoding, and add a concise “How the evidence was validated” panel. Do not expose capabilities or signed URLs.
- **Complexity:** Medium; 0.5-1 day plus tests.
- **Verification:** Approval and API-only fixtures render distinct accurate labels; portal still has no approval controls; frontend tests/build pass; production asset hash is recorded after deployment.

### P1-4 - Document tenant dependencies and portable assignment

- **Exact issue:** The canonical artifact necessarily contains tenant resource IDs; the portal webhook connection and Quick Form single-user assignment are owner-tenant resources. `.flow-sdk/bindings.json` is ignored, and the current guide does not provide one short end-to-end import/bind/assign checklist.
- **Why it matters:** Public browsing is zero-credential, but running the full Flow in another tenant is not zero setup.
- **Required fix:** Document exact resource categories, minimum entitlements, connection creation, registry binding, reviewer assignment, model availability, API Workflow deployment and webhook URL handoff. Use placeholders, never owner secrets.
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

1. No native Maestro evaluation run exists.
2. Submission documentation/source provenance remains contradictory and not clone-ready outside the remediated Flow build path.
3. Current live evidence does not cover every requested scenario/failure/replay case.
4. Portal presentation understates Analyze Files and contains stale/dead/encoding artifacts.
5. A second-tenant import and resource-binding rehearsal has not been performed.

## Release interpretation

The deployed demo is functional and financially safe, so the project is **READY WITH LIMITATIONS**, not a failed build. P0-1 is closed; it is not submission-final until P0-2 is closed or explicitly accepted as a limitation. None of the remaining gaps justifies changing deterministic reconciliation or custody data.

