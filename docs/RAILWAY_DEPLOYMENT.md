# Railway deployment — TransferIQ AI

Deployment preparation is implemented. **No Railway build, deployment, HTTPS request, volume test, or UiPath cloud execution has been performed.** Local verification is recorded below. All records and PDFs are fictional; the service performs no real transfers, settlement, trading, or financial corrections.

## Architecture and exact configuration

Use one Railway Python application service and attach one persistent volume at `/data`. Use one replica and one Uvicorn worker. SQLite and documents share that volume; no database service or additional worker is required.

| Setting | Exact value |
|---|---|
| Repository/root directory | `/` (repository root), **not `/backend`** |
| Railway configuration file | `/railway.json` |
| Builder | Railpack |
| Python | 3.13, selected by `.python-version` |
| Custom build command | Leave unset |
| Dependency installation | Railpack runs `pip install -r requirements.txt`; this includes `backend/requirements.txt` |
| Start command | `python -m backend.start` |
| Pre-deploy command | Leave unset |
| ASGI application | `backend.main:app` |
| Bind | `0.0.0.0`, port from Railway's `PORT` |
| Workers / replicas | 1 / 1 |
| Volume mount / required mount | `/data` / `/data` |
| Health-check path / timeout | `/health` / 300 seconds |
| Restart policy | On failure, maximum 3 retries |

`railpack.json` explicitly includes the nested requirements file in the install step while retaining the generated inputs. The root wrapper avoids duplicating dependency versions. Build steps install dependencies only: they do not import the application, create SQLite, migrate, or seed. See [Railpack Python detection](https://railpack.com/languages/python/) and [configuration and additional inputs](https://railpack.com/config/file/). Railway settings are declared in [railway.json](../railway.json); supported fields are described in [Railway's configuration reference](https://docs.railway.com/config-as-code/reference).

## Environment variables

Set these on the application service before its first successful deployment:

| Name | Value | Purpose |
|---|---|---|
| `APP_ENV` | `production` | Require a configured API key |
| `DATA_DIR` | `/data` | Required persistent storage location |
| `API_KEY` | A newly generated, strong secret | `X-API-Key` authentication; never commit or log it |
| `SEED_DEMO_DATA` | `1` | Add missing fictional TRF-1001 through TRF-1005 fixtures and PDFs at startup |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` | Bounded SQLite lock wait |
| `MAX_DOCUMENT_BYTES` | `10485760` | Maximum uploaded PDF bytes |
| `PYTHONDONTWRITEBYTECODE` | `1` | Avoid runtime bytecode writes to source folders |
| `PYTHONUNBUFFERED` | `1` | Flush runtime logs promptly |

Railway supplies `PORT`, `RAILWAY_ENVIRONMENT_ID`, and `RAILWAY_VOLUME_MOUNT_PATH`; do not invent or override its volume variables. If you deliberately set `PORT`, use an integer from 1 to 65535 and configure public networking to that same target port. `SEED_DEMO_DATA` accepts only `0` or `1`; `0` skips seeding but still migrates and recovers pending documents. Leaving it at `1` is safe on restarts. Existing rows and registered sample PDFs are preserved.

Do not set `DATABASE_URL`, `WEB_CONCURRENCY`, or any UiPath variables for this deployment. This backend only uses SQLite. UiPath connection binding is a separate future task. `APP_PUBLIC_BASE_URL`, session and CORS placeholders in `.env.example` are not currently consumed. Railway runtime deliberately ignores local `.env` files.

## GitHub and Railway setup

1. Create an empty GitHub repository under the intended owner. A private repository is suitable; authorize Railway's GitHub integration for that repository. This workspace was not a Git repository when inspected. If still uninitialized, run the following from `C:\Projects\TransferIQ-AI`, substituting your repository URL:

   ```powershell
   git init
   git branch -M main
   git add .
   git diff --cached --name-only
   # Review the staged list: no .env, data/, .venv/, PDFs, databases, or tenant secrets.
   git commit -m "Prepare TransferIQ backend for Railway"
   git remote add origin https://github.com/YOUR-OWNER/TransferIQ-AI.git
   git push -u origin main
   ```

   If Git is already initialized, use its existing branch and remote instead of repeating initialization. `.gitignore` excludes local secrets, databases, runtime PDFs, virtual environments, and tenant bindings. Do not upload a ZIP containing ignored local files.

2. In Railway, create a new project and choose **Deploy from GitHub repo**. Select the repository and deployment branch. Keep only this application service; do not add PostgreSQL or Redis. If an automatic deployment starts before configuration is complete, it will fail closed; configure the service and redeploy.
3. Set service **Root Directory** to `/` (or leave the default repository root). Confirm it uses the root `railway.json`, Railpack, and start command above. Leave custom build and pre-deploy commands empty. Do not select `/backend`: imports use the `backend` package from the repository root.
4. Attach a persistent volume to this service with **Mount Path `/data`**. Confirm one replica. Set all environment variables listed above and deploy the staged changes. `requiredMountPath` plus the runtime check prevent silently creating a database on ephemeral storage.
5. Open the deployment's build logs, then deployment/runtime logs. Expect successful dependency installation, `schema_ready`, `fictional_demo_seed_complete`, and `application_ready`. On a fresh seeded volume the seed counts are 112 rows and 16 PDFs. Later restarts normally report zero additions. A modified/preexisting database may add fewer records.
6. In service **Settings → Networking → Public Networking**, choose **Generate Domain**. Use the resulting HTTPS URL and the application's `PORT`. Visit `https://YOUR-DOMAIN/health`, then `/docs`. No custom domain is required.

The current Railway flow and logging entry points are described in [Railway quick start](https://docs.railway.com/quick-start). Volumes are mounted at runtime, not during builds or pre-deploy commands: [volume documentation](https://docs.railway.com/volumes) and [pre-deploy limitations](https://docs.railway.com/deployments/pre-deploy-command).

## Startup, readiness, and persistence

`backend.start` configures JSON console logs and starts one Uvicorn worker. The application lifespan then:

1. Validates configuration and, on Railway, the actual `/data` mount before creating anything.
2. Creates private writable directories and probes storage permission. Multipart spool files also use `DATA_DIR/tmp`.
3. Opens `DATA_DIR/transferiq.db` with foreign keys, WAL, `synchronous=FULL`, a bounded busy timeout, and explicit transactions. SQLite temporary sorts use memory rather than ephemeral OS files. Existing versioned migrations run to schema version 3. An empty database is initialized; an unknown/incomplete schema is rejected. No reset/drop fallback exists.
4. Recovers pending document writes. If `SEED_DEMO_DATA=1`, inserts only missing deterministic fixture IDs and missing sample recipes. Existing customers, transfers, exceptions, uploads, document IDs, versions and references are not replaced. Existing sample bytes are integrity checked without rendering them again.
5. Marks the application ready and begins serving. `/health` verifies readiness and a live database query; it returns 200 with `status=ok` and `database=ok`. Initialization, recovery, or seeding failure stops startup with a nonzero exit status.

Registered PDFs that are missing or corrupt cause opt-in sample initialization to fail instead of silently creating replacement evidence. Restore the original bytes with the recorded checksum from a coordinated backup. Missing *unregistered* sample recipes are generated normally. Pending-upload recovery may change a previously pending record to READY or FAILED, according to its stored bytes; it does not overwrite evidence.

```text
/data/
  transferiq.db             # SQLite; WAL/SHM companion files may also exist
  documents/                # Private immutable PDF bytes
  staging/                  # Pending document writes
  tmp/                      # Temporary multipart spooling
  sample_exports/           # Optional manual seed CLI exports, not startup output
  verification/             # Optional developer verification/visual QA artifacts
```

Logs go to stdout, not to a source-tree file. Startup/error events include UTC time, phase, and exception class; SQL parameters, request credentials, document contents, and raw exception tracebacks are omitted. Access logging is disabled. Use the Railway deployment log viewer and search for `startup_failed`, `schema_ready`, `fictional_demo_seed_complete`, or `application_ready`.

Health checks gate deployment readiness; they are not continuous uptime monitoring. A service using a volume has a brief interruption during redeployment because deployments cannot concurrently mount the same volume. Keep a single replica. See [health checks](https://docs.railway.com/deployments/healthchecks) and [volume constraints](https://docs.railway.com/volumes/reference).

## Verify the public API and authentication

Run in PowerShell, replacing only the domain. Enter the **same** API key configured in Railway; the prompt masks it and the script does not print it:

```powershell
$baseUrl = 'https://YOUR-DOMAIN'
$secret = Read-Host 'Railway API_KEY' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
$headers = @{ 'X-API-Key' = $apiKey }

Invoke-RestMethod "$baseUrl/health"
Invoke-RestMethod "$baseUrl/api/transfers/TRF-1002"
1001..1005 | ForEach-Object { Invoke-RestMethod "$baseUrl/api/transfers/TRF-$_" }
(Invoke-WebRequest -UseBasicParsing "$baseUrl/docs").StatusCode

$run = Invoke-RestMethod -Method Post "$baseUrl/api/transfers/TRF-1002/reconcile" `
    -Headers $headers -ContentType 'application/json' -Body '{}'
$run | Select-Object reconciliationRunId, status, summary
Invoke-RestMethod "$baseUrl/api/transfers/TRF-1002/exceptions" -Headers $headers
$documents = Invoke-RestMethod "$baseUrl/api/transfers/TRF-1002/documents" -Headers $headers
$documents.items | Select-Object documentId, documentType, documentStatus, checksumSha256
```

A new reconciliation returns 201; unchanged input reuses the persisted result with 200. The untouched TRF-1002 fixture has one unresolved quantity exception. Reconciliation persists analysis and audit history; it does not apply financial corrections. Preserve any intentional data changes when comparing results.

Confirm a request **without** headers to `/api/transfers/TRF-1002/reconciliation` or a document download returns 401. `POST /api/transfers` also requires the key. Only core fictional read APIs, health, OpenAPI, and Swagger remain public. There is no reset endpoint and no public correction endpoint. Swagger's **Authorize** accepts the same API key for protected routes.

## Verify persistence after redeployment

This check uses a newly created fictional transfer so reseeding cannot disguise lost storage. In the same terminal:

```powershell
$body = @{
    clientId='CLI-001'; deliveringFirmId='FIRM-SUMMIT'; receivingFirmId='FIRM-NORTHSTAR'
    sourceAccountId='ACC-SRC-001'; destinationAccountId='ACC-DST-001'; transferType='FULL'
} | ConvertTo-Json
$creationHeaders = @{
    'X-API-Key'=$apiKey
    'Idempotency-Key'=('railway-persistence-' + [guid]::NewGuid().ToString('N'))
}
$created = Invoke-RestMethod -Method Post "$baseUrl/api/transfers" `
    -Headers $creationHeaders -ContentType 'application/json' -Body $body
$beforeTransfer = $created | ConvertTo-Json -Depth 20 -Compress
$beforeRunId = $run.reconciliationRunId
$document = $documents.items | Where-Object { $_.documentStatus -eq 'READY' } | Select-Object -First 1
$downloadUrl = "$baseUrl/api/documents/$($document.documentId)/download"
# Local verification files stay under the local configured DATA_DIR.
$localDataDir = & .\.venv\Scripts\python.exe -c "from backend.core.config import Settings; print(Settings.from_environment().data_dir)"
$checkDir = Join-Path $localDataDir 'verification/railway'
New-Item -ItemType Directory -Force $checkDir | Out-Null
$beforeFile = Join-Path $checkDir 'before.pdf'
$afterFile = Join-Path $checkDir 'after.pdf'
Invoke-WebRequest -UseBasicParsing $downloadUrl -Headers $headers -OutFile $beforeFile
$beforeHash = (Get-FileHash $beforeFile -Algorithm SHA256).Hash
```

Use Railway's **Redeploy** action for the same service without replacing or detaching the volume. Wait for readiness, then run:

```powershell
Invoke-RestMethod "$baseUrl/health"
$after = Invoke-RestMethod "$baseUrl/api/transfers/$($created.transferId)"
if (($after | ConvertTo-Json -Depth 20 -Compress) -ne $beforeTransfer) { throw 'Transfer changed or was lost' }
$afterRun = Invoke-RestMethod "$baseUrl/api/transfers/TRF-1002/reconciliation" -Headers $headers
if ($afterRun.reconciliationRunId -ne $beforeRunId) { throw 'Reconciliation history changed or was lost' }
$afterDocument = Invoke-RestMethod "$baseUrl/api/documents/$($document.documentId)" -Headers $headers
if ($afterDocument.checksumSha256 -ne $document.checksumSha256) { throw 'Document metadata changed' }
Invoke-WebRequest -UseBasicParsing $downloadUrl -Headers $headers -OutFile $afterFile
if ((Get-FileHash $afterFile -Algorithm SHA256).Hash -ne $beforeHash) { throw 'PDF bytes changed' }
if ($beforeHash.ToLowerInvariant() -ne $document.checksumSha256) { throw 'PDF checksum mismatch' }
'Persistence checks passed'
$headers.Clear(); $creationHeaders.Clear(); Remove-Variable apiKey, secret
```

Do not delete the volume to repair a deployment. Enable Railway volume backups and test restoration of the database **and** documents together. Coordinate backups with paused writes or a SQLite-consistent procedure; copying a live `.db` alone can miss WAL transactions. [Railway volume backups](https://docs.railway.com/volumes/backups) are available without adding a database service. No cloud backup/restore test has been executed here.

## Local verification and troubleshooting

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_deployment.py -q
.\.venv\Scripts\python.exe -m pip check
# Start the exact deployment entry point locally; existing .env supplies API_KEY.
$env:SEED_DEMO_DATA = '1'
$env:PORT = '8001'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -m backend.start
# In another terminal:
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8001/api/transfers/TRF-1002
```

The launcher reads `PORT` from the process environment (default 8000); a `PORT` line in local `.env` does not configure the launcher. Application settings such as `DATA_DIR`, `API_KEY`, and `SEED_DEMO_DATA` do read local `.env`. Production rejects an empty key. The exact deployment launcher binds all interfaces; use `scripts/start-backend.ps1` for the existing localhost-only development workflow.

| Symptom | Action |
|---|---|
| Python not detected / nested requirements missing | Use root `/`, include `requirements.txt`, `backend/requirements.txt`, `.python-version`, and `railpack.json` in GitHub. Do not remove the install input override. |
| `No module named backend` | Use root `/` and exact start command, not `uvicorn main:app` from `/backend`. |
| `startup_failed`, phase `configuration` | Check production API_KEY, APP_ENV, DATA_DIR=/data, and the attached `/data` volume. Do not manually spoof Railway's volume variables. |
| Failure during `storage` | Check volume permissions/capacity and mount; application never falls back to ephemeral storage. |
| Failure during `schema` | Preserve volume and backup. Inspect schema version against supported migrations; fix the migration. Never reset/drop tables as a workaround. |
| Failure during `demo_documents` | Restore missing/corrupt registered PDF bytes and verify their checksum. Check mount support for hard links. Do not replace document IDs or metadata to hide corruption. |
| Build succeeds but health times out | Inspect runtime logs; confirm one worker, PORT binding, health path, volume and startup phases. More retries cannot fix invalid configuration. |
| `401` on protected API | Send the configured value in `X-API-Key`; authorize Swagger. Restart/redeploy after rotating the key. |
| Empty transfer list / TRF-1002 missing | Set SEED_DEMO_DATA=1 and redeploy with the existing volume. Never use a reset endpoint or build-time seed. |
| SQLite busy / `503` | Keep one worker/replica; avoid simultaneous CLI seeding and requests. Retry with the same idempotency key when supported. Never delete WAL/database files. |
| Lost data after redeploy | Check the same volume is still attached at /data; stop further mutations and investigate/restore a coordinated backup. |

### Executed evidence

Executed on 2026-11-01 with the existing Windows `.venv`, Python 3.13.14:

| Command / check | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | Final run: **243 passed, 0 failed**, 66.74 seconds; one existing upstream Starlette TestClient deprecation warning |
| Initial focused `-m pytest tests/test_deployment.py -q` | 24 passed, 0 failed in 18.22 seconds; the subsequent migration-process-exit test also passed in the full suite (25 deployment tests total) |
| `-m pip install --dry-run -r requirements.txt` | Exit 0; existing virtual environment already satisfies the root wrapper and backend dependencies |
| `-m pip check` | Exit 0; no broken requirements |
| Exact `python -m backend.start` | Executed twice by the HTTP subprocess test against isolated persistent storage; fresh initialization, seed, Swagger, five transfers, authorization, upload/download, reconciliation, restart and byte/ID preservation passed |
| Failed migration subprocess | Nonzero startup exit; schema sentinel preserved; no application-ready event |
| PowerShell parser validation | Both startup/document scripts and all five deployment-guide PowerShell blocks parsed without errors |
| Static artifact checks | Changed Python modules parsed; both JSON configurations parsed; deployment-guide local links resolved |

Tests use isolated temporary directories, including actual subprocess HTTP requests and restart checks; they do not run against the persistent development database. The existing SQLite foreign-key/WAL, initialization, transactional migration, seeding, financial precision and audit tests also passed. No dependency was added. Railpack/Railway CLI was unavailable locally, so an actual Linux image build was not run. Railway mount behavior, public HTTPS routing, live redeployment and backup restore remain manual acceptance checks.

### Files changed for this increment

Created: `.python-version`, `requirements.txt`, `railpack.json`, `railway.json`, `backend/start.py`, `backend/core/logging.py`, `backend/core/runtime.py`, `tests/test_deployment.py`, and this guide.

Modified: `.env.example`, `README.md`, `ARCHITECTURE.md`, `PROJECT_PLAN.md`, `backend/core/config.py`, `backend/main.py`, `backend/api/routes.py`, `backend/database/session.py`, `backend/database/seed.py`, `backend/database/seed_documents.py`, `tests/test_database.py`, `scripts/render_pdf_qa.py`, `scripts/verify-documents.ps1`, and `docs/DOCUMENT_API.md`.

The existing dependency versions, financial calculations, database migration definitions, API authentication policy, and UiPath artifacts were preserved. No production data reset, repository push, or cloud deployment was performed.
