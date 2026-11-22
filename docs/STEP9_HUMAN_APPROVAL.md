# Step 9 — isolated human review

> Historical implementation and incident record. The Quick Form failure below
> was subsequently resolved. Use STEP9_MANUAL_FORM_VERIFICATION.md and the
> Step 11 1.1.1 record for current approval/rejection evidence.

Implemented on 2026-11-06. Backend redeployment is now verified: real Maestro run creation returned 201 and plan preview returned 200. The compiled Flow passes product validation; TRF-1001 completed CLEAN. **No Step 9 Action Center task or human completion has yet been observed.** TRF-1002's real agent and preview succeed, but Quick Form creation fails with UiPath HTTP 400 / incident 170000 (`Failure in the AppTasks request`). One same-user GUID comparison had the same failure; the exact rejected property is unconfirmed. See [actual tests and instance IDs](STEP9_TEST_RESULTS.md) and [API contracts](STEP9_API_CONTRACTS.md).

## Flow and form

**Current diagnostic stage:** the original four-outcome form is backed up under ignored `data/verification/step9/quickform-fix/original/`. The current 76-node candidate uses Quick Form 1.9, one read-only summary, optional comments, and Approve Disposition/Reject. Request Evidence/Escalate are not currently present in this minimal canvas; their backend contracts remain implemented. The full-form tables below describe the original Step 9 design, not completed live acceptance. See [form comparison](STEP9_QUICK_FORM_FIX.md) and [November 9 agent-data diagnosis](STEP9_NOV9_DATA_DIAGNOSIS.md).

The existing Flow ID and Autonomous Agent are preserved. Successful independent agent validation leads to `BuildResolutionPlan`, `PreviewResolutionPlan`, `ValidateResolutionPlan`, then `TransferOperationsReview`. Invalid or incomplete investigations retain the existing evidence-review result. CLEAN bypasses the agent and form. `enableIXP=false` remains the default; Step 9 preview accepts `NOT_PROCESSED_IXP_DISABLED`. Enabling IXP retains the existing setup/evidence stops, not a claimed extraction integration.

`TransferOperationsReview` uses the real `uipath.human-in-the-loop.quick-form` definition, currently version 1.9 from the user's working reference. It is not a Script or Mock. Recipient channel is Action Center; single-user assignment reads `quickFormReviewerEmail` from ignored `.flow-sdk/runtime.local.json` at build time. The review-reference input must match the intended reviewer; it is still explicitly an unverified demo reference, not an authenticated financial authorization. CLEAN bypasses review. An explicitly blank reviewer fails plan construction.

| Form fields | Direction |
|---|---|
| Transfer ID, fictional client reference, exception count | Read-only |
| Agent summary, SEC-103 corporate-action facts, SEC-104 shortage facts | Read-only |
| Verified evidence IDs, backend-validated proposed dispositions | Read-only |
| Plan ID/hash, overall risk, demo scope notice | Read-only |
| `reviewerComments`, `additionalInformation` | Editable text, maximum 2,000 characters each downstream |

No editable disposition, quantity, plan binding, or reviewer identity is accepted from the form. The model's summary is labelled untrusted narrative. Displayed exception facts and proposed actions come from backend records, not free-form model text.

| Button / source port | Script | Backend outcome |
|---|---|---|
| Approve Disposition / `outcome-approve-disposition` | `ApproveDisposition` | `APPROVE` |
| Request Evidence / `outcome-request-evidence` | `RequestEvidence` | `REQUEST_EVIDENCE` |
| Escalate / `outcome-escalate` | `EscalateDisposition` | `ESCALATE` |
| Reject / `outcome-reject` | `RejectDisposition` | `REJECT` |

Every branch checks the actual form output's `Action` and reads `reviewerComments`/`additionalInformation` by field ID. The selected branch writes the Flow variable `reviewDecision`. The exact previewed plan version/hash accompany the decision. A correlation string ending in `:TransferOperationsReview` is a **demo event reference, not a verified task ID**. Actual Action Center task identity must be captured separately during the live test.

API and validation failures after investigation return `REVIEW_FAILED`. The initial Quick Form 1.0 lacked a supported error port; the minimal 1.9 candidate retains native task-failure behavior. Task-service creation/runtime failures remain UiPath incidents and do not authorize a disposition. Cancellation, expiry or an unanswered task is not approval.

## State and permitted effects

```mermaid
stateDiagram-v2
    [*] --> PREVIEWED: independently validate and hash
    PREVIEWED --> DECIDED: record one exact-bound demo review
    DECIDED --> EXECUTED: approve / request evidence / escalate
    DECIDED --> REJECTED: reject, no disposition rows
```

Each immutable plan is version 1; changed content requires a new plan ID and review. A run permits at most five plans. Decisions and disposition history are append-only. Exact retries return the existing result; different payloads or reused review events conflict. Backend data/evidence fingerprints and the latest reconciliation must still match at decision, execution and verification. The existing demo run expiry applies throughout.

TRF-1002 approval acknowledges SEC-103's independently verified explanation and creates an open escalation for SEC-104. The 20-share shortage stays unresolved. Request Evidence creates evidence-request dispositions; Escalate creates open operations dispositions; Reject creates no disposition records. Missing basis opens a basis case, never a fabricated value. No path changes custody snapshots, staging quantities, underlying reconciliation exceptions or transfer lifecycle status.

After execution, the Flow independently reads the plan, latest reconciliation, verification and audit. It checks the exact decision, hash/version, expected dispositions, unchanged exceptions, quantity verification and all three required audit events. The structured report includes the requested IDs, summary, plan status, review outcome, evidence, dispositions, unresolved exceptions, document status, verification, workflow outcome and scoped audit URL. It explicitly reports `transferCompleted=false`, zero corrections and unverified demo identity.

## Demo security and reproducibility

Run creation automatically issues a strong random, run-scoped `reviewCapability`; judges do not configure a TransferIQ API key or connection. The capability is required for plan/decision/execution writes and expires with the isolated run. Knowing a public plan ID/hash is insufficient. Normal Step 5 run creation cannot be replayed to acquire review authority. Private mutation routes remain protected and fail closed without verified-review configuration.

The backend does not authenticate a UiPath callback or verify the reviewer string. The audit is explicitly `UNVERIFIED_DEMO_REFERENCE` / `demoOnly=true`. A run owner can submit constrained synthetic decisions directly; these are **not evidence of human participation**. Real human participation is established only by the actual UiPath task and resumed execution. Do not use the demo ledger for real approval authority.

Capabilities remain in the private registry and runtime HTTP context. Do not publish raw debug inputs/variables/headers or creation responses; redact `reviewCapability` and `X-Demo-Capability`. Final reports and forms omit them. Demo reads are public to holders of run IDs, so enter fictional/non-sensitive comments only. Quotas, rate limits and one-worker isolation remain enforced. Review writes have zero automatic retries; an operator may resume using the same immutable request after inspecting state.

## Backend deployment procedure (redeployment now verified)

This workspace has no `.git` directory (`git rev-parse --show-toplevel` fails). No commit/push or Render redeployment was performed by this task. Copy the reviewed source changes into the existing GitHub checkout connected to Render; do not copy `.env`, `data`, runtime traces, capabilities, caches or tenant-local configuration.

Backend files: `backend/api/resolution.py`, `backend/api/public_limits.py`, `backend/database/migrations.py`, `backend/models/resolution.py`, `backend/models/entities.py`, `backend/schemas/resolution.py`, `backend/services/resolution.py`, `backend/services/demo_runs.py`, `backend/main.py`. Include the Step 9 tests, Flow source/scripts/compiled artifact and documentation when committing the project. Preserve existing `.uipx` via the CLI; do not edit it by hand.

Other changed files: `tests/test_resolution.py`, `tests/test_step9_flow.py`, `tests/test_migrations.py`, `tests/test_maestro_contract.py`, `tests/test_step8_agent.py`, `tests/test_judging.py`, `scripts/maestro-local-runner.mjs`; the existing `.flow-sdk/TransferIQ_Reconciliation.flow.ts` and canonical `.flow`; four new `.flow-sdk/scripts/` files (`build-resolution-plan.js`, `validate-resolution-plan.js`, `record-review-input.js`, `validate-review-result.js`); these three Step 9 documents plus root README/architecture/project plan. The final artifact was baseline-merged to preserve the existing canvas layout; keep it when staging rather than replacing it with an unmerged compile.

In that checkout:

```powershell
git status --short
git diff --check
# Review/stage the specific changed files; exclude all secrets/runtime data.
git add backend tests scripts/maestro-local-runner.mjs docs/STEP9_HUMAN_APPROVAL.md docs/STEP9_API_CONTRACTS.md docs/STEP9_TEST_RESULTS.md README.md ARCHITECTURE.md PROJECT_PLAN.md
# Stage the reviewed Maestro project source/artifact separately; inspect staged paths.
git diff --cached --stat
git commit -m "Add isolated demo review plans and Maestro Quick Form"
git push
```

In Render, deploy that exact commit on the existing service. Keep the existing `/data` persistent disk, environment and one-worker launcher. Schema v4 is additive; registry v2 adds review capability storage. Startup migrates existing databases without reseeding over prior records. Back up the existing persistent data using the established deployment procedure; never delete/reset it to apply this change. Follow [Render settings](RENDER_DEPLOYMENT.md).

Acceptance after deployment: `/health` must return 200; OpenAPI must contain `/api/demo/runs/review`; a single valid review creation must return 201 (or 200 on exact retry), not 404, and contain the capability without logging its value. Use that run for scoped reconciliation, preview, decision and verification. A malformed review request should be 422. Stop and inspect `Retry-After` on 429; do not launch repeated debug runs to probe readiness.

## Real task completion procedure (pending Quick Form creation)

1. Validate the final artifact and refresh solution resources using the installed Flow skill. Debug the existing project with `transferId=TRF-1001`, `enableIXP=false`; confirm CLEAN without a form.
2. Obtain the signed-in UiPath identity with `uip login status --output json`. Debug TRF-1002 with that `reviewerReference` and IXP false. Preserve a sanitized execution ID and locate the actual waiting task. No task ID/link is available yet.
3. In the same UiPath organization/tenant, open **Action Center → My Actions**, filter Pending and search **TransferOperationsReview - TRF-1002**. Match its displayed plan ID/hash with the waiting run before submitting. The assistant must not complete it for the user.
4. Inspect the split evidence and unchanged SEC-104 shortage; optionally enter fictional comments, then choose **Approve Disposition**. Resume/inspect the same instance rather than creating another run. Require `REVIEWED_WITH_OPEN_EXCEPTIONS`, SEC-104 difference `-20`, `VERIFIED_DEMO_STATE` and persisted audit records.
5. Start a separate TRF-1002 run, wait for its distinct task, and have the user select **Reject**. Require `REVIEW_REJECTED` and no disposition rows. Separately run TRF-1004 and TRF-1005 and allow the user to complete their review tasks. Never substitute test-double outputs when reporting these live results.

The assistant will provide the exact task identity/link after observing a real task. Manual completion remains pending; no real approval success is claimed.
