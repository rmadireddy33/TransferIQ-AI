# TransferIQ AI architecture

This document describes the implemented 1.1.2 architecture. Older Step documents are historical evidence, not current-state specifications.

## System context

    Public portal user ---- read-only GETs ----> React portal
    Authorized operator --- session/CSRF/idempotency --> React portal
    React portal ---------- same-origin API -------> Render FastAPI
    Render FastAPI -------- durable state ---------> SQLite and PDFs on /data
    Render FastAPI -------- one authenticated POST -> UiPath HTTP Webhook
    Manual Trigger --------\
                            > Maestro TransferIQ_Reconciliation
    Portal Webhook --------/
    Maestro Flow ---------- bounded demo APIs -----> Render FastAPI
    Maestro Flow ---------- file request ----------> TransferIQ_Document_Retrieval
    Retrieval Workflow ---- real attachment -------> Autonomous Agent + Analyze Files
    Maestro Flow ---------- review task -----------> Action Center Quick Form
    Maestro Flow ---------- verify/audit ----------> Render FastAPI

One Render service hosts the API and compiled React application. It uses one worker and one persistent disk because SQLite and PDF integrity depend on a single coordinated writable store. No external database, Redis service, or public document directory exists.

## Persistence boundaries

DATA_DIR is repository-relative ./data locally and /data on Render.

    DATA_DIR/
      transferiq.db                       private application database, schema v4
      documents/                          private generated/uploaded PDFs
      staging/ and tmp/                   bounded document write areas
      competition/transferiq.db           anonymous demo-run registry, schema v2
      competition/runs/{DEMO-id}/         isolated run SQLite database and PDFs
      portal/transferiq.db                PEX lifecycle registry, schema v3

The private database, each demo-run database, and the portal registry have different purposes and authorization boundaries. Public demo routes never open the private session factory. The React build is served from application source, not from DATA_DIR.

## Backend components

The backend uses FastAPI, SQLAlchemy, Pydantic, and SQLite.

- Core/private APIs manage fictional clients, firms, accounts, securities, transfers, immutable source positions, receiving staging, reconciliation, and private documents. X-API-Key is required, including for GETs.
- The packaged demo catalog exposes five precomputed fictional scenarios and never queries private live storage.
- Demo-run APIs create bounded, TTL-governed, run-isolated state. They expose only the selected allowlisted scenario and issue a capability for constrained review writes.
- Portal APIs authenticate an operator with a short-lived signed HttpOnly cookie. The only cookie-authenticated mutation, investigation start, requires a non-empty session-bound CSRF header and an idempotency key before persistence or dispatch. Read-only GETs remain CSRF-exempt. Portal APIs persist sanitized workflow state by executionRequestId and expose operator-scoped paginated history without exposing registry internals.
- Resolution services bind plans to transfer, reconciliation, evidence versions, hashes, capabilities, expiry, and decisions. Demo execution records dispositions; it never mutates custody or staging quantities.
- Audit events are append-only and final verification independently rereads plan, decision, disposition, reconciliation, and audit state.

See [API_SURFACES.md](docs/API_SURFACES.md) for exact routes.

## Portal-to-audit lifecycle

1. The operator authenticates to the portal. A start request requires the signed session, its matching `X-CSRF-Token`, and an `Idempotency-Key`; authentication and CSRF validation happen before PEX persistence or webhook dispatch.
2. The backend persists PENDING before dispatch, sends one bounded webhook POST, and records TRIGGERED on acceptance. HTTP 200 is not workflow completion.
3. The Flow creates and binds an isolated review run, reconciles it, and advances the PEX record to INVESTIGATING.
4. CLEAN cases persist COMPLETED/CLEAN without document retrieval, an agent, or a human task.
5. Investigation cases obtain API references and optionally a real PDF attachment, invoke the agent, and independently validate the structured result.
6. Plan preview persists AWAITING_HUMAN_REVIEW. A real Quick Form captures Approve or Reject in Action Center.
7. The Flow records the decision, applies only the allowed demo disposition, rereads state, verifies the audit, and persists COMPLETED or FAILED.
8. The portal reads the same PEX record with bounded polling. Reloading does not start another run. The authenticated history route lists existing PEX records newest-first globally or filtered by an allowlisted transfer ID, and both views link to the same persisted six-stage detail view.

Portal statuses are PENDING, TRIGGERED, INVESTIGATING, AWAITING_HUMAN_REVIEW, COMPLETED, FAILED, and TIMED_OUT. Browser polling expiration never changes server state.

## Maestro Flow

The canonical Flow has 81 nodes and 86 edges. Manual Trigger and authenticated Portal Webhook share one graph. Major node families are:

- input normalization and allowlist validation;
- isolated run creation and deterministic reconciliation HTTP calls;
- CLEAN/investigation/failure decisions;
- automated document retrieval API Workflow;
- TransferInvestigationAgent with built-in Analyze Files;
- independent structured-output and evidence validation;
- plan preview, Quick Form, decision, execution, verification, and audit;
- explicit controlled return/error terminals.

The editable TypeScript source is reproducible with the pinned toolchain. It preserves canonical node IDs, edge tuples, agent input contract, Quick Form outcome IDs, and trigger/resource references. Tenant-local bindings remain ignored. Details are in [MAESTRO_SOURCE_REPRODUCIBILITY.md](docs/MAESTRO_SOURCE_REPRODUCIBILITY.md).

## Document evidence

TransferInvestigationAgent supports two honest routes:

- AGENT_ANALYZE_FILES when a real PDF job attachment is supplied. The built-in Analyze Files tool extracts document fields.
- API_ONLY when file analysis is disabled or no valid document is available. API evidence remains usable, but document validation is not claimed.

For automated portal runs, TransferIQ_Document_Retrieval selects the allowlisted run-scoped corporate-action notice, obtains bounded base64 content, validates metadata/checksum/type/ownership, and returns a real file resource. It does not pass a URL string as a file.

Extracted security ID, action type, split ratio, dates, and evidence reference are initially unverified document evidence. Flow validation compares them with GET /api/demo/runs/{runId}/corporate-actions; mismatches or missing fields stay REVIEW_REQUIRED.

IXP-in-Flow is unavailable in the Community tenant and is not part of this path. enableIXP=false is preserved. No document extraction alone can authorize a correction.

## Financial and security invariants

- All data is fictional and allowlisted.
- Delivering custody positions and receiving staging positions are separate and immutable.
- Decimal arithmetic and deterministic policy remain authoritative.
- Unknown cost basis is unknown, never zero.
- Agent output and PDF content are untrusted evidence.
- Demo plan capabilities are scoped, short-lived, and absent from read responses.
- The portal cannot approve, reject, upload arbitrary files, or call private APIs.
- A completed workflow is not necessarily a completed transfer.
- TRF-1002 approval leaves SEC-104 at UNRESOLVED/-20 with unchanged positions and transferCompleted=false.
- Private resolution writes fail closed because production-grade reviewer identity is not configured.
- Secrets, webhook headers, signed file URLs, capabilities, and document contents are excluded from public responses.

## Deployment and portability

Production uses Render with DATA_DIR=/data, one instance/worker, build-time frontend compilation, and runtime-only database initialization. UiPath solution 1.1.2 contains the Flow, document-retrieval API Workflow, HTTP Webhook connection resource, Autonomous Agent configuration, and Quick Form configuration. The 1.1.2 release changes canonical artifact reproducibility only; retained end-to-end functional execution evidence remains from 1.1.1.

The root [`TransferIQ_Reconciliation.uis`](TransferIQ_Reconciliation.uis) is a checksum-recorded Studio Web source export containing both UiPath projects. It is not an activated package. A judge imports it into a separate tenant, replaces the reviewer and webhook bindings, then publishes/deploys a judge-owned version by following [TRANSFERIQ_UIS_RUN_GUIDE.md](TRANSFERIQ_UIS_RUN_GUIDE.md).

Another tenant must supply its own entitled organization/tenant/folder, HTTP Webhook connection, eligible single-user Quick Form reviewer, Agent/Analyze Files availability, ignored Flow bindings, and deployed webhook URL. No owner tenant identifier or secret is a portable default.

## Current limitations

- One bounded native Maestro CLEAN evaluation scored 1.0; native inline-Agent evaluation remains blocked because node-scoped evaluation cannot supply the preserved upstream file expression.
- A second-tenant import/binding rehearsal has not been retained.
- Demo reviewer references are not suitable for real financial authority.
- Real ACATS, settlement, trading, and custody mutation are deliberately absent.
- Release/source provenance is maintained outside this workspace and is not inferred here.
- Additional live scenario coverage remains a backlog item; portal presentation labels and the active status timeline are reconciled with persisted backend state.
