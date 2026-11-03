# Credential-free TransferIQ judging

The existing Maestro Automate Flow calls real, anonymous synthetic-run APIs. Judges supply only `transferId`; no TransferIQ API key, HTTP connection, token, secret or owner credentials are required. **The updated backend must first be deployed to Render.** UiPath still requires the judge's own signed-in account, an entitled tenant and permission to import/run Maestro Automate projects.

## Owner rollout

Deploy this repository revision to the existing Render service manually. Keep Root Directory blank, build `pip install -r backend/requirements.txt`, start `python -m backend.start`, one worker, disk `/data`, and health `/health`. Preserve the existing private `API_KEY`; judges never use it. Use these non-secret settings:

```dotenv
DATA_DIR=/data
APP_ENV=production
SEED_DEMO_DATA=1
PUBLIC_DEMO_ENABLED=1
PUBLIC_DEMO_REQUESTS_PER_MINUTE=60
PUBLIC_DEMO_GLOBAL_REQUESTS_PER_MINUTE=300
DEMO_EXECUTION_ENABLED=1
DEMO_MAX_RUNS=50
DEMO_RUN_TTL_HOURS=24
DEMO_STORAGE_LIMIT_MB=128
```

No build-time database writes or new services are required. Startup creates a versioned synthetic-run registry alongside the existing private database, without resetting it. Public runs seed their own fixed fixtures on demand, independently of `SEED_DEMO_DATA`, which controls the private demonstration database.

After deployment, from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_public_demo --base-url https://transferiq-api.onrender.com
```

This performs actual HTTP calls and executes the emitted Flow scripts/decisions in a **local contract harness**. It is not evidence of a UiPath runtime execution. It exits unsuccessfully if the deployed schema lacks the new routes.

## Open and run the Flow

1. Open the repository in VS Code with the UiPath Maestro extension installed. Open `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/TransferIQ_Reconciliation.flow` in its visual designer. Preserve the surrounding project, Automate marker, `operate.json` and parent solution; do not import a loose file as BPMN or Case.
2. Use your own UiPath sign-in and tenant with Maestro Automate/managed HTTP runtime access. For Studio Web, run `uip solution upload .\maestro\TransferIQ_Reconciliation --output json` from the repository root and open the returned `DesignerUrl`, then open `TransferIQ_Reconciliation` on the Flow canvas. This uploads the existing solution; do not use `--force` on an unrelated existing cloud solution. No TransferIQ connection resources are required.
3. Inspect all five HTTP Request nodes: authentication is **Manual**, with no credentials. The generated runtime uses `ImplicitConnection`, which is UiPath's built-in manual HTTP transport, not a connection the judge must create. No Authorization or X-API-Key headers exist.
4. Select the designer's Debug/Run action. At `StartTransferInvestigation`, enter `transferId` as `TRF-1001`. Run again with `TRF-1002`. Each invocation automatically generates a non-secret request identifier and creates its own isolated demo run.
5. Inspect the actual execution trace, `NormalizeReconciliation`, the `RequiresInvestigation` decision and the final `result`. Keep the UiPath instance ID as cloud execution evidence. `result.demoRunId` correlates the synthetic backend audit; it is not an authentication token.

Supported CLI equivalents, after signing into your own tenant:

```powershell
.\scripts\build-maestro.ps1
uip solution resources refresh --solution-folder .\maestro\TransferIQ_Reconciliation --output json
# Debug uploads/updates the matching Studio Web solution; use your own imported copy.
uip maestro flow debug .\maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation --inputs '{"transferId":"TRF-1001"}' --output json
uip maestro flow debug .\maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation --inputs '{"transferId":"TRF-1002"}' --output json
```

Wait for each debug to finish before starting another. These commands execute real HTTP operations against the synthetic sandbox. A successful local validation alone does not establish runtime success. No solution was uploaded or cloud run executed as part of this revision; see [verification](ZERO_CREDENTIAL_VERIFICATION.md).

The supplied artifact defaults to `https://transferiq-api.onrender.com`. Only developers changing hosts need `scripts/configure-maestro.ps1 -BackendBaseUrl https://YOUR-HOST` followed by a rebuild. No ConnectionId argument is required.

## Anonymous API contract

All paths below are relative to the HTTPS base URL. Only TRF-1001 through TRF-1005 are accepted for run creation.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/demo/runs` | Body `{"transferId":"TRF-1002"}`; non-secret `Idempotency-Key` header (16–128 letters/digits/period/underscore/colon/hyphen). Returns runId, transferId, UTC epoch expiresAt and LIVE_SYNTHETIC_BACKEND marker; 201 new, 200 retry. |
| GET | `/api/demo/runs/{runId}/transfer` | Selected run's synthetic transfer details |
| GET | `/api/demo/runs/{runId}/delivering/accounts/{accountId}/positions` | Source account from the transfer response; immutable snapshots |
| GET | `/api/demo/runs/{runId}/receiving/accounts/{accountId}/positions` | Destination account from the transfer response; selected transfer's staging only |
| POST | `/api/demo/runs/{runId}/reconcile` | Body `{}`; existing deterministic engine; 201 new result or 200 reused result |
| GET | `/api/demo/runs/{runId}/reconciliation` | Latest real backend reconciliation result |
| GET | `/api/demo/runs/{runId}/exceptions` | Real persisted exception details |
| GET | `/api/demo/runs/{runId}/documents` | Seeded non-evaluation fictional PDF metadata |
| GET | `/api/demo/runs/{runId}/documents/{documentId}/download` | Actual PDF bytes, checked against recorded hash; restricted to selected run/transfer |
| GET | `/api/demo/runs/{runId}/audit` | Sanitized persisted action/timestamp history; no private logs, paths or UiPath execution claims |
| GET | `/api/demo/transfers`, `/api/demo/transfers/{transferId}` | Separate PRECOMPUTED_SYNTHETIC_SAMPLE view; never a live execution |
| GET | `/health`, `/docs`, `/redoc`, `/openapi.json` | Readiness and API contracts |

The position/document/exception lists accept bounded `limit` and `offset`. The current Flow requests up to 100 positions and fails on truncation. Account IDs must match the selected transfer; unrelated accounts/documents return 404. Run creation rejects unknown transfer IDs with 422. Unknown run IDs return 404; retained expired runs return 410. After cleanup, expired IDs return 404.

Idempotency-Key is a caller-generated deduplication value, **not an API key or access token**. No authorization is derived from it. A retry with the same key/transfer returns the same run within its retention window; using the key for another transfer returns 409. Once the run expires and is cleaned up, the key can create a new run. Use a new key for an intentional new execution. The Flow generates and reuses its key across HTTP retries automatically.

Example without authentication:

```powershell
$base = 'https://transferiq-api.onrender.com'
$requestId = [guid]::NewGuid().ToString('N')
$run = Invoke-RestMethod "$base/api/demo/runs" -Method Post -ContentType 'application/json' -Headers @{'Idempotency-Key'=$requestId} -Body '{"transferId":"TRF-1002"}'
$root = "$base/api/demo/runs/$($run.runId)"
Invoke-RestMethod "$root/transfer"
Invoke-RestMethod "$root/reconcile" -Method Post -ContentType 'application/json' -Body '{}'
Invoke-RestMethod "$root/exceptions"
$documents = Invoke-RestMethod "$root/documents"
Invoke-WebRequest "$root/documents/$($documents.items[0].documentId)/download" -OutFile "$env:TEMP/transferiq-fictional.pdf"
Invoke-RestMethod "$root/audit"
```

## Isolation, protection and limits

Each run owns `DATA_DIR/competition/runs/{runId}/transferiq.db` and a `documents/` directory. The registry is `DATA_DIR/competition/transferiq.db`. Public endpoints never use the private root database/session or private uploaded documents. Existing schema initialization, seeders, Decimal calculations, immutable custody rules, transaction handling and PDF integrity checks are reused. The seed contains fixed fictional scenarios only; the API cannot accept arbitrary holdings or evidence.

Run IDs are public correlation values, not confidential access credentials. Anyone knowing a run ID can read its synthetic output or request the same idempotent reconciliation. There is no public list of all runs and no caller-supplied run ID at creation. Reconciliation does not change custody or staging positions, apply corrections, approve decisions or settle transfers. Concurrent work is serialized by a bounded lock; a busy service returns 503. Duplicate reconciliation requests reuse the database fingerprint/result and do not append duplicate completion audits.

Defaults: 50 retained runs, 24-hour lifetime, 128 MiB storage admission budget with 5 MiB reserved per new fixed-fixture run, 5 creation requests/client/minute and 20 total/minute, plus 60 public requests/client/minute and 300 total/minute. Creation retries also consume rate budget. POST bodies are bounded to 4096 bytes, including streamed bodies. Global/client limiter state is bounded and resets on restart; persisted run/storage quotas survive restarts. All writable data stays under DATA_DIR. One worker and one instance are required. These limits cannot guarantee availability under deliberate public quota exhaustion; retry after quota expiry or use operator-managed capacity/edge protection.

Expired registry-owned synthetic directories are removed on subsequent run creation, after validating their resolved paths. This cleanup never touches private transfers, PDFs or audit history. Unexpired runs survive restart/redeployment. Public run output uses no-store. Health remains outside the public budget. The middleware does not trust arbitrary X-Forwarded-For headers; a hosting proxy may share a conservative client budget.

All original `/api/clients`, `/api/firms`, `/api/accounts`, `/api/securities`, `/api/transfers`, delivering/receiving, corporate-action, reconciliation and private document endpoints retain `X-API-Key` authentication. Transfer creation, private reconciliation and arbitrary upload remain protected. Public reset, correction, approval, unrestricted update, workflow trigger and filesystem/log endpoints are absent (404/405), not silently authorized.

## Expected scenarios and remaining dependencies

| Transfer | Direct | Explained | Unresolved | Expected quantity outcome |
|---|---:|---:|---:|---|
| TRF-1001 | 7 | 0 | 0 | CLEAN |
| TRF-1002 | 5 | 1 | 1 | INVESTIGATION_REQUIRED |
| TRF-1003 | 0 | 1 | 0 | CLEAN |
| TRF-1004 | 7 | 0 | 0 | CLEAN, but separate missing-cost-basis review remains |
| TRF-1005 | 0 | 0 | 1 | INVESTIGATION_REQUIRED; unsupported correction is not applied |

CLEAN is quantity reconciliation, not settlement or approval. Missing/invalid responses, 401/403/404/422, transport failures and unsuccessful reconciliation route to FAILED. Quotas return 429; timeouts/backend unavailability fail safely. HTTP nodes have a 30-second timeout, one retry and explicit failure terminals. The normalization script validates IDs, counts, evidence, classifications and complete position lists; no API response is hardcoded.

IXP, Autonomous Agent invocation, Human Task/Quick Form approval, correction application and public workflow triggers are **not implemented** in this Flow. Future IXP/agent read context can use this run's document, exception and audit GETs without TransferIQ credentials. Real IXP still needs an entitled tenant, published extraction model and supported PDF transport. Real agent investigation needs a published agent and its model/tool permissions. Human tasks need licensed users, task configuration and verified reviewer identity. Implementing future writes requires run-scoped allowlists, proposal/version binding, verified approvals, idempotency and quotas; opening private correction APIs is not an acceptable shortcut. There are no fake endpoints claiming those integrations work.

## Reproduce the backend locally

From a clone of the repository, in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Own operator secret for the PRIVATE API, never needed by anonymous demo calls.
$env:API_KEY = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
$env:DATA_DIR = './data'
$env:APP_ENV = 'development'
$env:SEED_DEMO_DATA = '1'
$env:DEMO_EXECUTION_ENABLED = '1'
.\.venv\Scripts\python.exe -m backend.database.init_db
.\.venv\Scripts\python.exe -m backend.database.seed
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\start-backend.ps1 -NoReload
# In a second terminal; install Node.js for the local graph harness:
.\.venv\Scripts\python.exe -m scripts.verify_public_demo
```

No UiPath credentials are needed to run backend tests or public HTTP requests. UiPath Cloud cannot reach localhost; self-hosted Flow reproduction requires a reachable HTTPS backend. Keep `.env`, databases, PDFs and personal tenant configuration out of Git. `.env.example` contains only non-secret defaults and blank secret placeholders.
