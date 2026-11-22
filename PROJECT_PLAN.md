# TransferIQ AI project plan and status

Current release: **UiPath solution 1.1.1**  
Current assessment: **READY WITH LIMITATIONS**  
Current canonical Flow: **81 nodes / 86 edges, Valid**

This plan records implemented milestones and remaining work. Historical Step documents preserve evidence from the version named in each file; they do not override the current status below.

## Completed milestones

| Milestone | Delivered outcome |
|---|---|
| Steps 1-2: core backend | FastAPI/SQLAlchemy/Pydantic/SQLite service, fictional entities, immutable source positions, receiving staging, idempotent transfer creation, private API authentication, and seed data. |
| Step 3: reconciliation | Decimal comparison, corporate actions, identifier mappings, cost-basis handling, persisted exceptions, five allowlisted scenarios, and historical runs. |
| Step 4: private documents | Generated/private PDFs, validated uploads, metadata/download APIs, checksums, generated storage keys, pending-write recovery, and migrations. |
| Step 5: anonymous demo runs | TTL/quota-bound isolated SQLite/PDF runs, credential-free synthetic APIs, Flow HTTP orchestration, CLEAN and investigation routing, and failure terminals. |
| Step 6: live Maestro proof | Real cloud traces for primary scenarios and bounded error behavior. |
| Step 7: IXP exploration | File and evidence contracts were explored. IXP-in-Flow was confirmed unavailable in the Community tenant; it is not claimed as implemented. |
| Step 8: Autonomous Agent | Real TransferInvestigationAgent, structured recommendations, independent output validation, API evidence, and controlled failures. |
| Step 9: human review | Real Approve/Reject Quick Form, capability-scoped demo plan preview/decision/execution, independent verification, append-only audit, and verified approval/rejection paths. |
| Step 10A: portal | React/TypeScript/Vite portal, five public fictional scenarios, read-only evidence views, same-origin FastAPI hosting, and responsive UI. |
| Step 10B: portal trigger | Signed operator session, CSRF/idempotency controls, authenticated HTTP Webhook, durable PEX correlation, and shared Manual/Webhook Flow graph. |
| Step 10C: status | Accurate lifecycle projection, terminal-aware bounded polling, reload-safe tracking, paginated operator-scoped investigation history, audit/transfer links, and workflow-vs-transfer completion distinction. |
| Step 11: document analysis | Automated fictional PDF retrieval, real Agent Analyze Files attachment, deterministic comparison to corporate-action API, API-only fallback, and live 1.1.1 approval/rejection/CLEAN evidence. |
| Reproducibility remediation | Source check 0/0, clean compile 81/86, product-valid candidate, semantic comparison, binding template, and pinned CLI 1.205.0. |

## Verification baseline

- Backend: **481 passed**, no failures or skips; one known Starlette/httpx deprecation warning.
- Frontend: **30 passed**, production build successful.
- Canonical Flow: product validation **Valid**.
- Editable source: **0 errors / 0 warnings**; clean compile **81 nodes / 86 edges**.
- Solution: **1.1.1 Active / Successful**.
- Real retained 1.1.1 evidence: TRF-1001 CLEAN; TRF-1002 Analyze Files approval and rejection; unchanged positions; verified audit.

These are recorded audit/remediation results, not tests rerun by every documentation update.

## Current priorities

### P0 - documentation and provenance

- Keep root, deployment, judge, and environment guidance aligned with release 1.1.1.
- Treat old incident and milestone documents as historical evidence.
- Keep tenant bindings and secrets outside source control.
- Maintain source/package/deployment provenance in the owner's external version-control process; this workspace does not assert it.

### P1 - evaluation and portable rehearsal

- Populate and run native Maestro whole-flow and agent/tool evaluations.
- Rehearse import, binding, reviewer assignment, validation, and activation in a second tenant.
- Retain only bounded additional live evidence when it closes a material scenario gap.

### Completed - demo clarity

- The active transfer and PEX views distinguish `AGENT_ANALYZE_FILES`, `API_ONLY`, and document evidence unavailable using sanitized persisted state.
- The unused legacy progress component and active-source encoding artifacts were removed.
- The active timeline renders six backend-derived stages and separates workflow completion from unresolved brokerage exceptions.
- Authorized operators can browse paginated persisted PEX history globally or within a selected transfer and reopen the existing timeline without creating another execution; historical null outcome and verification fields remain explicitly unrecorded.

### P2 - optional scope

- Add Request Evidence/Escalate outcomes only if explicitly added to scope and live-verified.
- Optionally expose a non-secret build identifier and document coordinated SQLite/PDF backup restoration.

## Acceptance invariants

Future changes must preserve:

- fictional data only;
- SQLite and private generated document storage under DATA_DIR;
- immutable source custody and receiving staging quantities;
- Decimal/scaled deterministic financial calculations;
- unknown cost basis never fabricated as zero;
- no correction authorized from AI extraction alone;
- scoped/idempotent writes and append-only audit;
- secrets and tenant identifiers outside source;
- explicit unavailable/failure states instead of simulated integrations;
- enableIXP=false unless a supported, verified tenant capability is deliberately introduced;
- workflow completion distinct from brokerage transfer completion.

## Out of scope

- real clients, holdings, ACATS, trading, settlement, or custody mutation;
- production identity/authorization for financial approval;
- public arbitrary uploads, corrections, resets, or approval controls;
- PostgreSQL, MySQL, MongoDB, Redis, or another database service;
- claims that IXP-in-Flow ran in the Community tenant;
- deployment merely to validate documentation.

## Authoritative references

- [Final project audit](docs/FINAL_PROJECT_AUDIT.md)
- [Feature completeness matrix](docs/FEATURE_COMPLETENESS_MATRIX.md)
- [Submission gap list](docs/SUBMISSION_GAP_LIST.md)
- [Judge reproduction guide](docs/JUDGE_REPRODUCTION_GUIDE.md)
- [Render deployment](docs/RENDER_DEPLOYMENT.md)
- [Flow source reproducibility](docs/MAESTRO_SOURCE_REPRODUCIBILITY.md)
- [Portal status](docs/STEP10C_PORTAL_STATUS.md)
- [Agent document analysis](docs/STEP11_AGENT_DOCUMENT_ANALYSIS.md)
