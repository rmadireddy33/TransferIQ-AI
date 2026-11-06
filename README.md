# TransferIQ AI

**Intelligent Brokerage Account Transfer Exception Resolution**

A hackathon demonstration using fictional clients, firms, securities, accounts, and financial information. No real ACATS connection, securities transfer, trading, or settlement is implemented.

## Current status

Step 9 is implemented locally: a real `TransferOperationsReview` Quick Form, isolated demo resolution plans/decisions/dispositions, additive SQLite migrations and independent verification/audit. The Flow validates without warnings. **Render still returns 404 for the new review-run route; real Step 9 task generation and human completion are pending deployment.** Financial reconciliation rules and custody/staging quantities are unchanged; IXP remains disabled by default. See [human review and deployment](docs/STEP9_HUMAN_APPROVAL.md), [API contracts](docs/STEP9_API_CONTRACTS.md) and [actual test results](docs/STEP9_TEST_RESULTS.md).

Step 8 adds the real `TransferInvestigationAgent` Autonomous Agent, independently validated recommendations, and `enableIXP=false` by default. The supplemental-reference GET is now deployed on Render and returns 200. A new real Maestro TRF-1002 run returned INVESTIGATION_COMPLETED: SEC-103's split explained, SEC-104's shortage retained, IXP explicitly skipped, missingEvidence empty, and agent input matched the fetched reference data. TRF-1001 also returned CLEAN; both runs retained unchanged positions and zero corrections. See [post-deployment verification](docs/STEP8_DEPLOYED_VERIFICATION.md). Cost-basis-only exceptions now enter investigation. See [Step 8 integration](docs/STEP8_AGENT_INTEGRATION.md) and [actual tests and limitations](docs/STEP8_AGENT_TEST_CASES.md). No financial corrections or approvals were added.

Step 7 preparation extends the existing Flow with optional `corporateActionPdf`, explicit missing-evidence/failure outcomes and deterministic reference validation. **The real in-Flow IXP model still needs Studio Web configuration; extraction has not succeeded or been claimed.** The current `CorporateActionExtractor` Script is a labelled setup-required stop, not an extractor. The run-scoped corporate-action GET is now live and was used by the real agent. Step 8 bypasses the setup-stop by default. Follow [the exact Step 7 setup and test boundaries](docs/IXP_STEP7_SETUP.md) and [the installed CLI/SDK capability findings](docs/IXP_TOOLING_CAPABILITIES.md) before replacing that stop with the real Extract document node.

Judges can execute real synthetic reconciliation through the live anonymous `/api/demo/runs` APIs. Each run has isolated SQLite/PDF state, idempotent retries and quotas. **The Flow needs no TransferIQ key, secret or HTTP connection.** Actual Maestro debug runs returned CLEAN for TRF-1001 and INVESTIGATION_REQUIRED for TRF-1002/TRF-1005. Unknown-ID cloud attempts safely returned FAILED but were masked by HTTP 429; direct API validation returned 422. Private APIs retain X-API-Key authentication. See [actual cloud evidence and Studio Web link](docs/MAESTRO_LIVE_EXECUTION.md) and [judge setup](docs/ZERO_CREDENTIAL_DEMO.md).

The user deployed the backend at https://transferiq-api.onrender.com; earlier live checks confirmed health and sample API responses. Render uses the same backend launcher and one persistent disk at `/data`. Subsequent local changes are not automatically deployed. Follow [the Render settings and manual deployment guide](docs/RENDER_DEPLOYMENT.md).

Railway backend deployment preparation is complete: Railpack configuration, one-worker startup, `/data` volume enforcement, runtime migrations, opt-in missing-only demo seeding, readiness, and structured logs. **No Railway deployment has occurred.** The current backend suite passes 243 tests, including real HTTP startup/restart and uploaded-PDF persistence. See [exact Railway setup, environment variables, verification and troubleshooting](docs/RAILWAY_DEPLOYMENT.md).

Step 5 provides the existing **Maestro Automate Flow** under `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/`. Its five Manual HTTP calls create an isolated run, fetch transfer/source/staging context and reconcile using actual previous-node outputs. Python retains all financial calculations. Product validation and real cloud debug executions are now verified; the debug CLI uploaded the existing solution to Studio Web. No permanent Orchestrator publication or new Render deployment was performed in this execution task. See [designer setup](docs/MAESTRO_STEP5_SETUP.md).

```powershell
# From repository root; no cloud execution:
.\scripts\build-maestro.ps1
code --reuse-window .\maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation\TransferIQ_Reconciliation.flow
# Requires the running local backend:
.\.venv\Scripts\python.exe -m scripts.verify_maestro_local
```

Step 2 implements the FastAPI backend, SQLAlchemy 2.x/Pydantic v2 models and contracts, persistent SQLite, core read APIs, API-key-protected transfer creation, deterministic sample seeding, and isolated Pytest tests. Receiving records are transfer staging positions, not settled custody holdings.

Step 3 adds deterministic reconciliation, verified synthetic reference evidence, cost-basis checks, and persisted exception history. Step 4 adds authenticated PDF upload/metadata/download APIs, persistent document storage, and 16 reproducible fictional PDFs. Approval workflows, frontend, IXP extraction, and Railway deployment remain unimplemented. See [Document API and commands](docs/DOCUMENT_API.md), [IXP handoff plan](docs/IXP_INTEGRATION_PLAN.md), and [Step 4 verification and generated paths](docs/STEP4_VERIFICATION.md). See [Reconciliation rules, endpoints, scenarios, and Swagger instructions](docs/RECONCILIATION.md) and [Step 3 verification](docs/STEP3_VERIFICATION.md). See [ARCHITECTURE.md](ARCHITECTURE.md), [PROJECT_PLAN.md](PROJECT_PLAN.md), [AGENTS.md](AGENTS.md), and [executed verification](docs/STEP2_VERIFICATION.md).

## Windows setup

Run from the project root with Python 3.11 or newer (verified with Python 3.13.14):

```powershell
Set-Location C:\Projects\TransferIQ-AI
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
```

Copy `.env.example` only if `.env` does not already exist. Activation is optional because commands explicitly use the project interpreter. To activate, use `.\.venv\Scripts\Activate.ps1` if permitted by your PowerShell policy.

Set `API_KEY` to a strong locally generated secret in `.env`, or supply it in the current terminal before starting the backend. For example, this creates a secret without printing it:

```powershell
$env:API_KEY = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
```

Process environment overrides the repository-root `.env`. Do not commit or log the key. A blank key makes private business requests return 503 locally and prevents production startup; a missing or incorrect `X-API-Key` returns 401 on private routes when a key is configured. Anonymous demo routes operate independently on fixed samples or isolated run storage; private authentication is never disabled. Reserved UiPath/frontend/session settings in `.env.example` are not consumed by the backend.

## Database initialization and fictional sample data

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db
.\.venv\Scripts\python.exe -m backend.database.seed
# Safe to repeat: existing records are preserved.
.\.venv\Scripts\python.exe -m backend.database.seed
```

Startup initializes an empty database automatically. Seeding is off by default; set `SEED_DEMO_DATA=1` to add missing fictional fixtures and PDFs during startup. Local storage defaults to `./data/transferiq.db`, resolved relative to the repository root regardless of the current working directory. Railway requires `DATA_DIR=/data`, with the persistent volume mounted there. There is no external database or `DATABASE_URL` configuration.

SQLite uses foreign keys, WAL, a 5000 ms configurable busy timeout, explicit transactions, and schema version 3 (with transactional upgrades from versions 1 and 2). Restarting never resets or overwrites existing data. Unknown or unversioned existing schemas are rejected rather than overwritten. Future schema changes require explicit migrations. Original snapshots and audit events reject updates, deletes, and replacement inserts.

Quantities are Python `Decimal` values stored as exact decimal text (up to 18 integer and 8 fractional digits); JSON quantities are strings. This avoids floating-point conversion under [SQLite NUMERIC affinity](https://www.sqlite.org/datatype3.html). All timestamps are UTC-aware. Step 3 stores exact basis amounts and checks lot completeness and quantity totals independently from position matching.

Seed fixtures are entirely fictional:

| Record | Identifiers |
|---|---|
| Delivering firm | Summit Wealth, `FIRM-SUMMIT` |
| Receiving firm | Northstar Securities, `FIRM-NORTHSTAR` |
| Clients | `CLI-001`, `CLI-002`; `.invalid` email domain |
| Source accounts | `ACC-SRC-001`, `ACC-SRC-002` |
| Destination accounts | `ACC-DST-001`, `ACC-DST-002` |
| Securities | `SEC-001` through `SEC-007`, fictional symbols and identifiers |
| Sample transfer | `TRF-1001`, DRAFT, `SIM-DEMO-1001` mock control number |
| Positions | Seven immutable source snapshots for `ACC-SRC-001`; seven matching staging rows for `TRF-1001` |

Seeding adds missing fixture IDs only and never updates existing records. The original Step 2 seed contains 31 rows; Step 3 adds 81 fixture rows for reference evidence, basis, and TRF-1002 through TRF-1005. The full seed CLI now also generates/registers 16 PDFs; an unchanged repeat inserts zero financial or document records. New scenarios use dedicated accounts; TRF-1001 is preserved.

The explicit seed CLI exports samples to `DATA_DIR/sample_exports`; changed generation inputs may create a new document version while retaining older versions. Automatic startup seeding instead checks existing sample recipes and integrity without re-rendering or replacing any registered PDF. It generates only missing recipes, and fails if registered sample bytes are missing or corrupt. Runtime uploads and downloads use `DATA_DIR/documents`, with temporary files under `DATA_DIR/staging` and `DATA_DIR/tmp`.

## Start and verify

```powershell
.\scripts\start-backend.ps1
# Without auto-reload, or on an alternate port:
# .\scripts\start-backend.ps1 -NoReload -Port 8001
```

The script binds to localhost. Stop with Ctrl+C. Swagger: <http://127.0.0.1:8000/docs>. OpenAPI: <http://127.0.0.1:8000/openapi.json>.

In a second PowerShell terminal:

```powershell
Set-Location C:\Projects\TransferIQ-AI
.\scripts\verify-backend.ps1
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/demo/transfers/TRF-1001
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

`verify-backend.ps1` makes real HTTP requests to all requested GET routes plus Swagger/OpenAPI and checks matching seeded positions. It expects the Step 2 fixtures. Use `-BaseUrl http://127.0.0.1:8001` for another port. Pytest uses `tmp_path` databases and explicit settings, never the persistent development database.

## Render startup

Use a **Starter Web Service**, **Python 3**, and leave **Root Directory blank**. Build with `python -m pip install -r backend/requirements.txt` and start with `python -m backend.start`. Attach one persistent disk at `/data`; set `APP_ENV=production`, `DATA_DIR=/data`, a strong `API_KEY`, and `SEED_DEMO_DATA=1`. The existing launcher reads Render's `PORT` and uses one worker. Health Check Path is `/health`; leave Pre-Deploy Command blank. See [all environment variables, disk setup, smoke tests and persistence checks](docs/RENDER_DEPLOYMENT.md).

## Railway startup

Configure root `/`, Railpack, one replica, one volume at `/data`, and start command `python -m backend.start`. Leave build and pre-deploy command overrides unset. Set `APP_ENV=production`, `DATA_DIR=/data`, a strong `API_KEY`, and `SEED_DEMO_DATA=1`. The launcher binds `0.0.0.0` using Railway's `PORT`, with one worker. `/health` becomes ready only after initialization, migrations, recovery and optional seeding succeed. See the [complete deployment guide](docs/RAILWAY_DEPLOYMENT.md) for all settings and manual acceptance checks.

## API contract

Every live `/api` route in the table below requires `X-API-Key`. `/health` is public. The separate `/api/demo/transfers` list/detail routes expose only the fixed five-scenario sample artifact, with explicit precomputed labels and rate limits. Swagger/OpenAPI remain public, but protected API execution requires Authorize.

All list responses use `{items, total, limit, offset}`. `limit` defaults to 50 and is capped at 100; `offset` defaults to zero. Pydantic responses use camelCase and reject extra creation fields. Lookup failures return 404; invalid creation references, ownership, firm roles, inactive records, or types return 422; database conflicts and mismatched idempotency payloads return 409. Domain errors contain `detail.code` and `detail.message`; request-schema validation uses FastAPI's standard 422 detail list.

| Method | Route | Behavior |
|---|---|---|
| GET | `/health` | Verify database connectivity; fictional-demo marker |
| GET | `/api/clients` | Paginated clients |
| GET | `/api/clients/{clientId}` | Client lookup |
| GET | `/api/firms` | Paginated brokerage firms |
| GET | `/api/accounts/{accountId}` | Account lookup |
| POST | `/api/transfers` | Create DRAFT transfer; requires `X-API-Key` |
| GET | `/api/transfers` | Paginated transfers |
| GET | `/api/transfers/{transferId}` | Transfer lookup |
| GET | `/api/transfers/{transferId}/assets` | Paginated receiving staging rows for this transfer |
| GET | `/api/delivering/accounts/{accountId}/positions` | Immutable positions at the latest snapshot date |
| GET | `/api/receiving/accounts/{accountId}/positions` | Paginated staging rows targeting this account; optional `transferId` filter |
| GET | `/api/securities` | Paginated security master |
| GET | `/api/securities/{securityId}` | Security lookup |

Creation records a request only: it does not copy positions, assign an ACATS control number, initiate processing, or settle assets. Both FULL and PARTIAL are supported as request metadata; partial asset selection is deferred. New transfers therefore have empty staging assets. The sample's seven staging rows are created by the seeder only.

Example creation, using the same secret configured in the server terminal (supply it securely in this terminal if different):

```powershell
$body = @{
    clientId = 'CLI-001'
    deliveringFirmId = 'FIRM-SUMMIT'
    receivingFirmId = 'FIRM-NORTHSTAR'
    sourceAccountId = 'ACC-SRC-001'
    destinationAccountId = 'ACC-DST-001'
    transferType = 'FULL'
} | ConvertTo-Json
$headers = @{
    'X-API-Key' = $env:API_KEY
    'Idempotency-Key' = 'local-demo-create-001'
}
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/transfers `
    -ContentType 'application/json' -Headers $headers -Body $body
```

The first request returns 201 and `Location`; replay with the same optional idempotency key and payload returns 200 and the same transfer. Reusing a key with changed content returns 409. Without a key, each POST creates a distinct request. Retrying callers should always supply a key and reuse it after transient failures. In Step 2 keys are scoped to the sole mutation and single service principal. Creation, audit, and idempotency records commit together.

Status starts at DRAFT. Structural transition validation exists in the service layer and database, but there is no status-update endpoint. See the documented transition graph in ARCHITECTURE.md. Reconciliation computes separate results; approval controls and the rules connecting those results to lifecycle transitions remain unimplemented.

## Source layout

```text
backend/
  api/             # Routers and request dependencies
  core/            # Validated environment configuration
  database/        # Engine/sessions, versioned bootstrap, init and seed CLIs
  models/          # SQLAlchemy entities, exact Decimal and UTC storage types
  schemas/         # Pydantic request/response contracts
  services/        # Transfers, reconciliation, PDF generation, private document storage
  main.py          # Application factory, lifespan, error handling
  start.py         # Deployment launcher; one Uvicorn worker, Railway PORT
  requirements.txt
scripts/
  start-backend.ps1
  verify-backend.ps1
tests/
  conftest.py
  test_api.py
  test_database.py
```

`maestro/` now contains the Step 5 SDK source, generated Flow, and UiPath solution scaffold. `frontend/` remains a placeholder. Runtime `.venv/`, `.env`, SQLite data and local UiPath binding/configuration files are excluded by `.gitignore`. This workspace is not currently initialized as a Git repository; no commits were created.

## Troubleshooting

- **Python cannot be accessed:** use `py -3.13` to create the environment and then `.venv\Scripts\python.exe`. The Windows Store alias may require execution outside a restricted tool sandbox. Do not switch to a global dependency install.
- **Module not found:** use the project interpreter and run from the repository root; reinstall with `-m pip install -r backend/requirements.txt`.
- **PowerShell script blocked:** follow your local execution-policy rules, or run `.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload` directly.
- **Port occupied:** stop the earlier server or pass `-Port 8001`; update verification URLs accordingly.
- **Empty GET results:** run the seed CLI against the same DATA_DIR used by the server, or opt in with SEED_DEMO_DATA=1 and restart. Startup seeding is disabled by default.
- **401 or 503 on POST:** configure API_KEY before server startup, restart after changing `.env`, and send the matching `X-API-Key`. Blank configuration fails closed.
- **SQLite lock/503:** avoid concurrent CLI seeding while serving writes, use one app worker, and retry with the same idempotency key. Never delete the database to clear a lock.
- **Storage permission error:** choose a writable DATA_DIR outside source-code directories; the application does not fall back to another location.
- **Unsupported schema:** preserve the database, make a SQLite-consistent backup, and implement an explicit migration. Do not delete or reset it as a startup workaround.
- **Test warning:** the tested Starlette version emits an upstream deprecation warning for its httpx TestClient. Tests still pass; no warning is suppressed.

Next verification: capture the unknown-ID 422 response in Maestro without public rate-limit interference. Valid scenarios already have actual instance/trace evidence. No TransferIQ connection binding is needed. UiPath tenant access, IXP, agents, approvals and financial corrections are not eliminated by anonymous backend access.


