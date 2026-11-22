# TransferIQ AI

TransferIQ AI is a fictional brokerage-transfer reconciliation demonstration. It combines a Render-hosted FastAPI/SQLite backend and React portal with a UiPath Maestro Flow, Autonomous Agent document analysis, Action Center Quick Form review, deterministic verification, and append-only audit evidence.

## Current verified release

- UiPath solution: **TransferIQ-AI 1.1.1**, active.
- Canonical Maestro Flow: **81 nodes / 86 edges**, product-valid.
- Editable Flow SDK source: reproducible, with **0 source errors / 0 warnings**.
- Flow toolchain: UiPath CLI **1.205.0** pinned in the Flow SDK lockfile. CLI 1.206.0 has a documented dynamic Quick Form validation regression.
- Backend regression: **481 passed**.
- Frontend regression: **30 passed**, production build successful.
- Hosting: one Render Python service with a persistent /data disk; FastAPI serves the React build at /portal.
- Real runtime evidence: portal-triggered CLEAN, approval, rejection, Autonomous Agent Analyze Files, Quick Form completion, independent verification, and audit.

The current audit and limits are documented in [FINAL_PROJECT_AUDIT.md](docs/FINAL_PROJECT_AUDIT.md), [FEATURE_COMPLETENESS_MATRIX.md](docs/FEATURE_COMPLETENESS_MATRIX.md), and [SUBMISSION_GAP_LIST.md](docs/SUBMISSION_GAP_LIST.md). The documentation-only reconciliation record is [DOCUMENTATION_RECONCILIATION.md](docs/DOCUMENTATION_RECONCILIATION.md).

## What the system does

1. A user browses one of five allowlisted fictional transfers in the public portal.
2. An authorized operator can browse global persisted investigation history, filter history inside an individual transfer, or start one investigation. The backend persists a PEX correlation record and sends one bounded authenticated webhook request to Maestro only for an explicit start.
3. Manual Trigger and Portal Webhook enter the same Flow graph. The Flow creates an isolated DEMO run and invokes deterministic reconciliation APIs.
4. CLEAN cases end without document retrieval, an agent, or a human task.
5. Investigation cases can retrieve the run-scoped fictional corporate-action PDF through TransferIQ_Document_Retrieval and pass a real file attachment to the Autonomous Agent's built-in Analyze Files tool.
6. AI-extracted fields remain untrusted until Flow logic compares them with the independent corporate-action API. If a file is unavailable, the agent uses an explicitly labeled API_ONLY route.
7. The backend previews a version-bound resolution plan. A real UiPath Quick Form captures Approve or Reject; the portal cannot approve.
8. The Flow records the decision, executes only allowlisted demo dispositions, rereads the plan, verifies final state, and exposes append-only audit records.

For TRF-1002, a completed approved workflow is REVIEWED_WITH_OPEN_EXCEPTIONS: SEC-103 is explained by verified 2-for-1 split evidence, while SEC-104 remains an unresolved 20-share shortage. positionsUnchanged=true, transferCompleted=false, and no financial correction is applied.

## Evidence and product boundaries

- All clients, firms, accounts, securities, PDFs, quantities, and actions are fictional.
- Original delivering custody positions and receiving staging quantities are immutable.
- Deterministic Python rules perform financial comparisons; AI and humans do not calculate or mutate positions.
- Analyze Files is the implemented document tool. **IXP-in-Flow is unavailable in the Community tenant and was not invoked.** enableIXP remains false.
- The current Quick Form has Approve and Reject outcomes only.
- Demo reviewer references are not production identity proof and cannot authorize private financial writes.
- There is no real ACATS, trading, settlement, or brokerage correction integration.

## Repository map

    backend/                         FastAPI, SQLAlchemy, Pydantic, SQLite services
    frontend/                        React, TypeScript, Vite portal
    maestro/TransferIQ_Reconciliation/
      TransferIQ_Reconciliation/     Canonical .flow and reproducible Flow SDK source
      TransferIQ_Document_Retrieval/ File-returning UiPath API Workflow
    docs/                            Current guides and historical milestone evidence
    tests/                           Backend, contract, graph, security, and regression tests
    data/                            Local runtime state; ignored and never deployed from source

## Local development

Requirements: Python 3.13, Node.js/npm, and PowerShell.

    py -3.13 -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
    Copy-Item .env.example .env
    # Set a local API_KEY in the ignored .env before starting protected APIs.
    & .\.venv\Scripts\python.exe -m backend.database.init_db
    & .\.venv\Scripts\python.exe -m backend.database.seed
    & .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

For frontend hot reload:

    npm ci --prefix frontend
    npm run dev --prefix frontend
    # http://127.0.0.1:5173/portal/

Application verification:

    & .\.venv\Scripts\python.exe -m pytest -q --tb=short
    npm test --prefix frontend -- --run
    npm run build --prefix frontend

These tests use isolated synthetic state and identified test doubles. They are not new UiPath executions.

## API boundaries

The OpenAPI document at /openapi.json is the route authority. Current groups are:

- public health and documentation: /health, /docs, /redoc, /openapi.json;
- precomputed public catalog: GET /api/demo/transfers and GET /api/demo/transfers/{transferId};
- anonymous isolated demo runs: /api/demo/runs..., including reconciliation, references, documents, corporate actions, plan review, verification, and audit;
- controlled portal operations: `/api/portal/session`, paginated `GET /api/portal/investigations`, explicit `POST /api/portal/investigations`, and PEX detail reads;
- private business/document routes under /api/..., protected by X-API-Key;
- protected resolution placeholders under /api/resolution-plans..., which fail closed because production-grade reviewer identity is not configured.

The exact route inventory is in [API_SURFACES.md](docs/API_SURFACES.md). Do not infer public authorization from an endpoint name: consult its documented boundary and OpenAPI security behavior.

## Deployment and UiPath reproduction

- Render configuration: [RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md).
- Judge and tenant setup: [JUDGE_REPRODUCTION_GUIDE.md](docs/JUDGE_REPRODUCTION_GUIDE.md).
- Source-to-Flow reproduction: [MAESTRO_SOURCE_REPRODUCIBILITY.md](docs/MAESTRO_SOURCE_REPRODUCIBILITY.md).
- Portal lifecycle: [STEP10C_PORTAL_STATUS.md](docs/STEP10C_PORTAL_STATUS.md).
- Document analysis: [STEP11_AGENT_DOCUMENT_ANALYSIS.md](docs/STEP11_AGENT_DOCUMENT_ANALYSIS.md).

Tenant imports must bind their own HTTP Webhook connection, select an eligible single-user reviewer for the Quick Form, and provide the target folder/resource values in ignored local bindings. Tenant identifiers and secrets must never be committed.

## Documentation convention

Root documents and the final audit describe the current architecture. STEP2 through STEP10 files are historical milestone and incident records; their statements are accurate for the date/version named in each file and are not the current release status. Step 11 and the reproduction guides supersede older setup instructions where they differ.

## Remaining limitations

- Native Maestro evaluation definitions currently have no data points or recorded evaluation run.
- A second-tenant import/binding rehearsal has not been retained.
- Current 1.1.1 live traces are not retained for every secondary scenario and negative case.
- Source-to-deployment commit provenance is managed outside this workspace and is not asserted here.
- Portal evidence labels now come from the persisted plan projection: `AGENT_ANALYZE_FILES`, `API_ONLY`, or document evidence unavailable. The active six-stage timeline uses backend-reported workflow state and keeps workflow completion distinct from transfer completion.
