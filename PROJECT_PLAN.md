# TransferIQ AI Project Plan

Step 1 is complete. Step 2 expands original Phase 2 to include the core models, reference/transfer APIs, immutable positions, receiving staging, synthetic seed, and creation audit/idempotency from original Phase 3. Step 3 now implements the deterministic comparison portion of Phase 5, including five scenarios, safe migration, reference evidence, protected endpoints, and historical runs. Step 4 now implements the private document repository, safe v3 migration, 16 fictional PDFs, protected binary downloads, integrity checks, and restart recovery. Mock ACATS processing, financial corrections, approvals, UI, and UiPath integrations remain unimplemented. Executed document checks are recorded in docs/STEP4_VERIFICATION.md. See docs/STEP3_VERIFICATION.md for executed checks. The phase table below is the longer-term roadmap; its verification checkpoints are acceptance criteria. Executed Step 2 verification is recorded in `docs/STEP2_VERIFICATION.md`.

Step 5 now uses five anonymous HTTP requests: create a synthetic run, retrieve transfer/source/staging context and reconcile. The existing 28-node Flow compiles and validates without Flow warnings. No TransferIQ connection or credential is required. Dependencies for cloud acceptance: deploy the run APIs to the existing HTTPS host and use an entitled UiPath tenant to execute scenarios and retain traces. See [setup](docs/MAESTRO_STEP5_SETUP.md) and [current verification](docs/ZERO_CREDENTIAL_VERIFICATION.md). This does not complete broader outbox, IXP, agents or human approval work.

| Phase | Deliverables | Dependencies | Verification checkpoint |
|---|---|---|---|
| 1. Foundation | Required folders, README, architecture, development guidelines, environment template, ignore rules. | None | Confirm all six files and eleven directories exist; inspect scope and placeholders; confirm no business code, workflows, dependency installation, or live integration claims. |
| 2. Backend and persistence bootstrap (implemented, plus requested core APIs) | FastAPI application, Pydantic configuration, SQLAlchemy sessions, initial SQLite v1 schema (now safely upgraded to v3), directory creation, core APIs and synthetic seed. | 1 | Test paths, foreign keys, schema initialization, restart persistence, API validation/authentication, immutability, precision, and idempotency. |
| 3. Core domain and mock systems | Transfer contracts and lifecycle, authenticated APIs, fictional fixture strategy, immutable custody snapshots, mock delivering/receiving firms, mock ACATS, security master. | 2 | Test valid/invalid transitions, forbidden custody update/delete, ownership checks, exact decimal round trips, deterministic mock outcomes, idempotent mutations, and atomic audit writes. |
| 4. Secure document repository (implemented) | Upload/download APIs, transfer-document relationships, immutable versions, hashes, access controls, interrupted-upload recovery. | 3 | Test authorized access, cross-transfer denial, traversal and oversized/type-invalid files, duplicate upload behavior, version history, interruption recovery, and persistence of metadata plus bytes after restart. |
| 5. Reconciliation and correction policy | Deterministic engine for all six exception categories, versioned proposals, adjustment ledger, approval persistence and enforcement. Specify allowlists/tolerances first. | 3, 4 | Cover clean match and each exception class; test fractional quantities, rounding, effective dates, unknown cost basis, ambiguous identifiers, stale evidence, rejected/expired/replayed approvals, concurrent apply, rerun reconciliation, and unchanged original custody. |
| 6. IXP evidence integration | Verify real tenant capabilities and credentials, extraction schema, adapter, evidence mapping and durable job tracking. | 4 | Run an actual extraction on fictional documents and retain sanitized job evidence; test low confidence, missing fields, wrong document correlation, provider failures, timeouts, duplicate results, and unavailable configuration. Mark live checks blocked if credentials are missing. |
| 7. Autonomous Agent investigation | Verify real agent resource and contract, scoped evidence tools, structured recommendations and backend validation. | 5, 6 | Run actual evidence-backed investigation; test unsupported recommendations, fabricated/missing evidence references, prompt injection, contradictory evidence, uncertainty, and denial of direct correction privileges. |
| 8. Maestro and human decision orchestration | Flow canvas orchestration, outbox dispatcher, real UiPath invocation, Human Quick Form approval verification, retry/recovery paths. Optional RPA only if retrieval requires it. | 5, 6, 7 | Verify an actual correlated end-to-end run; approve and reject paths; test unauthorized reviewer, self-approval, stale task, duplicate callback, ambiguous dispatch timeout, restart recovery, and no correction before verified authorization. Verify optional RPA separately if added. |
| 9. Operations frontend | React/TypeScript/Vite/Tailwind transfer views, document submission, exception evidence, status and audit views, secure operator/reviewer sessions. | 3, 4, 5; integrated status requires 8 | Test browser flows against real backend contracts, loading/error/empty states, access isolation, keyboard navigation, session/CSRF controls, and absence of service secrets in frontend assets. |
| 10. Railway deployment and demonstration | Build frontend for FastAPI, one service/worker/replica, one /data volume, runtime secrets, backup/restore procedure, fictional demo scenarios and operating guide. | 2-9 | Test fresh deployment, upgrade, restart and redeploy persistence, writable mounted storage, SQLite concurrency/WAL behavior, document retention, backup restore consistency, live UiPath callback reachability/authentication, and full success/rejection/failure demos. |

## Dependency sequence

Requested backend-only deployment preparation is complete independently of frontend/IXP/agent work: root Railpack configuration, persistent-volume startup checks, runtime-only migrations, missing-only demo seeding, production key enforcement and readiness. Verification: 243 local tests passed, including isolated real HTTP restarts and migration failure exit behavior. The [Railway operating guide](docs/RAILWAY_DEPLOYMENT.md) records exact configuration. This does not mark Phase 10 complete: actual Railway build/deploy, public HTTPS, mounted-volume redeployment persistence and backup restoration remain acceptance gates. No new UiPath nodes or UI were implemented.

```text
1 -> 2 -> 3 -> 4 -> 5
               4 -> 6
          (5, 6) -> 7
       (5, 6, 7) -> 8
       (3, 4, 5) -> 9; integrate orchestration views after 8
           (2-9) -> 10
```

No phase may claim completion solely from a mocked external response. Unit tests may use clearly labeled test doubles; actual UiPath verification is a separate gate. Record commands, observed results, failed checks, and blocked checks honestly. Each implementation phase must update documentation to match delivered behavior before advancing.

## Specialist routing for later work

Use UiPath platform guidance before making UiPath API calls, IXP guidance for extraction configuration, agent guidance for the Autonomous Agent, Maestro Flow guidance for Automate orchestration, and human-in-the-loop guidance for Quick Form authoring. Use RPA guidance only if retrieval automation is required. Product availability and resource contracts must be verified in the actual tenant; no tenant discovery or deployment is part of Phase 1.

## Immediate next implementation step

Judging now adds anonymous run-isolated execution and retains separately labelled precomputed samples. Private APIs remain protected. Redeploy this revision to Render, verify the anonymous routes, then run Maestro TRF-1001/TRF-1002 and inspect actual instance traces. No public workflow trigger exists; judges start the Flow within their own UiPath environment. Reproduction and remaining dependencies are documented in [JUDGING_ACCESS.md](docs/JUDGING_ACCESS.md).

The backend is already hosted on Render. Manually deploy the new revision to that same Starter service and /data disk using [RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md). Complete real HTTP and redeployment-persistence checks before claiming acceptance. The earlier Railway preparation remains an alternative. IXP/agent implementation and approval enforcement remain separate later work.


