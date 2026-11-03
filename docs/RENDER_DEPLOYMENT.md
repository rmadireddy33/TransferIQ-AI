# TransferIQ AI — manual Render deployment

Use one **Starter Python Web Service** and one persistent disk. This guide matches the existing `backend` package and its `backend.main:app` FastAPI application. The user has deployed https://transferiq-api.onrender.com. Redeploy the [credential-free judging revision](ZERO_CREDENTIAL_DEMO.md) to expose its new run-isolated synthetic APIs; private APIs remain protected. No database server, Docker, frontend, or additional worker is needed.

## Exact dashboard settings

| Render field | Value to enter |
|---|---|
| Service type | Web Service |
| Instance type | Starter |
| Root Directory | **Leave blank** (repository root; do not enter `backend` or `/backend`) |
| Language | Python 3 |
| Build Command | `python -m pip install -r backend/requirements.txt` |
| Start Command | `python -m backend.start` |
| Pre-Deploy Command | Leave blank |
| Instance count | 1 |
| Persistent disk name | `transferiq-data` |
| Persistent Disk Mount Path | `/data` |
| Initial disk size | 1 GB for this fictional demo; increase if needed |
| Health Check Path | `/health` |

The root must contain `backend/`, `.python-version`, and the documentation. The launcher imports `backend.main:app`, binds `0.0.0.0`, reads the process `PORT`, and explicitly sets `workers=1` with reload disabled. It ignores suggested concurrency values. The existing launcher is reused; no second startup script is needed. Railway/Railpack files are not used by this native Render setup.

Render defaults to the repository root when Root Directory is unset; its Python language label is **Python 3**. See [root directory behavior](https://render.com/docs/monorepo-support) and [Render FastAPI settings](https://render.com/docs/deploy-fastapi).

## Environment variables

Add these under the service's Environment settings before deployment:

| Name | Value |
|---|---|
| `PYTHON_VERSION` | `3.13.14` (matches the tested local interpreter) |
| `APP_ENV` | `production` |
| `DATA_DIR` | `/data` |
| `API_KEY` | Your own strong secret, generated once and stored securely; never use this description as the value |
| `SEED_DEMO_DATA` | `1` |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` |
| `MAX_DOCUMENT_BYTES` | `10485760` |
| `PYTHONDONTWRITEBYTECODE` | `1` |
| `PYTHONUNBUFFERED` | `1` |
| `PUBLIC_DEMO_ENABLED` | `1` |
| `PUBLIC_DEMO_REQUESTS_PER_MINUTE` | `60` |
| `PUBLIC_DEMO_GLOBAL_REQUESTS_PER_MINUTE` | `300` |
| `DEMO_EXECUTION_ENABLED` | `1` |
| `DEMO_MAX_RUNS` | `50` |
| `DEMO_RUN_TTL_HOURS` | `24` |
| `DEMO_STORAGE_LIMIT_MB` | `128` |

Render supplies `PORT` (normally `10000`) and `RENDER=true`. **Do not manually add `RENDER`, Railway variables, or a fake disk marker.** The application checks that `/data` is an actual mount. `PORT` does not need a manual override. Render's fully qualified `PYTHON_VERSION` overrides the existing `.python-version` file (`3.13`). See [Render environment variables](https://render.com/docs/environment-variables), [port binding](https://render.com/docs/web-services), and [Python version selection](https://render.com/docs/python-version).

Generate a unique API key with a password manager (at least 32 random bytes) and paste it into Render's secret environment field. Supply that same value as `X-API-Key` to protected APIs. Do not put it in Git, URLs, frontend variables, screenshots, or logs. Production startup rejects a blank key. On Render the application ignores local `.env` files entirely.

`SEED_DEMO_DATA` accepts `0` or `1`. Keep `1` for the five demo scenarios; rerunning it is safe. `0` skips demo additions but still runs initialization, migrations, and pending-document recovery. No `DATABASE_URL`, PostgreSQL configuration, UiPath secrets, or session placeholders are needed for this deployment.

## Create the service manually

1. Push the current repository to your Git provider. Include `backend/`, its requirements file, `.python-version`, and these changes. Review staged files before committing: `.env`, `.venv`, `data/`, database files, generated PDFs, and tenant credentials must stay excluded by the existing `.gitignore`. An empty Render disk will receive fictional fixtures; local uploads and reconciliation history are not copied automatically.
2. In Render choose **New → Web Service**, connect the existing repository, and select the branch containing these changes. Choose **Python 3** and **Starter**, then enter the exact commands above. Leave Root Directory blank.
3. Add the environment variables. Under **Advanced**, add the persistent disk with mount `/data` and health check `/health`. If the service already exists, attach the disk from its Disk page and set the health path in Settings. Do not run a seed or migration command in Build or Pre-Deploy.
4. Start the deployment yourself. The build only installs existing requirements. Watch deployment/runtime logs for `schema_ready`, `fictional_demo_seed_complete`, and `application_ready`. The first completely empty seeded database adds 112 fixture rows and 16 PDFs; an unchanged restart adds zero of each.
5. Open the HTTPS `onrender.com` URL shown on the service page, then `/health` and `/docs`. In Swagger, choose **Authorize** and enter the configured API key for protected operations.

Render disks are available only at runtime, not during build/pre-deploy or separate one-off jobs. Only files under the mount survive replacement of an instance. A disk restricts the service to one instance and causes a brief interruption on redeployment. See [persistent disk setup and limitations](https://render.com/docs/disks). `/health` checks readiness and SQLite connectivity without a key; Render uses HTTP health checks both for deployment readiness and ongoing health. See [health checks](https://render.com/docs/health-checks).

## Storage and safe startup

```text
/data/
  transferiq.db             # SQLite database and its adjacent WAL/SHM files
  documents/                # Private uploaded/generated PDFs in generated buckets
  staging/                  # Pending document writes
  tmp/                      # Multipart spool files
```

Local development continues to default to repository-relative `./data`. Render requires `DATA_DIR=/data` and a mounted disk before any directory or database is created. The API does not expose these files as a public static directory.

The existing lifespan runs initialization/migrations **after** the disk check. An empty database receives schema version 3; supported v1/v2 databases are upgraded transactionally. Unsupported or incomplete schemas fail startup with a nonzero exit instead of being dropped or reset. Foreign keys, WAL, a 5000-ms default busy timeout, `synchronous=FULL`, short explicit transactions, and in-memory SQLite temporary sorts remain enabled.

Startup recovers pending document writes, then optionally adds missing fixture IDs for TRF-1001 through TRF-1005. Existing customers, transfers, exceptions, source holdings, uploaded documents, and sample references are preserved. Registered sample recipes are checked without re-rendering; only missing recipes generate PDFs. Missing/corrupt registered sample bytes stop opt-in seeding for operator repair instead of silently changing a document ID. Recovery can mark previously pending uploads READY or FAILED based on their stored bytes.

Explicit developer seed/export commands remain available, but are unnecessary for deployment. Initialization never runs during build. Original private business APIs require X-API-Key, including GETs. Anonymous `/api/demo/runs` operations create isolated synthetic SQLite/PDF state under `/data/competition`; `/api/demo/transfers` list/detail remains precomputed. No reset or financial-correction endpoint is introduced. Follow [credential-free judge rollout and verification](ZERO_CREDENTIAL_DEMO.md); judges do not need the private key used in the operator checks below.

## Verify the live service

In PowerShell, replace only the host and enter the same secret saved in Render. This prompt does not print the key:

```powershell
$baseUrl = 'https://YOUR-SERVICE.onrender.com'
$secret = Read-Host 'Render API_KEY' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
$headers = @{ 'X-API-Key' = $apiKey }
Invoke-RestMethod "$baseUrl/health"
1001..1005 | ForEach-Object { Invoke-RestMethod "$baseUrl/api/transfers/TRF-$_" -Headers $headers }
(Invoke-WebRequest -UseBasicParsing "$baseUrl/docs").StatusCode
$run = Invoke-RestMethod -Method Post "$baseUrl/api/transfers/TRF-1002/reconcile" `
    -Headers $headers -ContentType 'application/json' -Body '{}'
$run | Select-Object reconciliationRunId, status, summary
$documents = Invoke-RestMethod "$baseUrl/api/transfers/TRF-1002/documents" -Headers $headers
$documents.items | Select-Object documentId, documentStatus, checksumSha256
```

Expect health 200 and all five transfer IDs. Reconciliation returns 201 for a new result or 200 for an unchanged replay; untouched TRF-1002 has one unresolved quantity exception. A request without the key to `/api/transfers/TRF-1002/reconciliation` or a document download must return 401. Reconciliation analyzes fictional evidence; it never applies a custody correction.

To verify persistence without letting reseeding mask a lost database, create a new fictional request and record a PDF hash before redeploying:

```powershell
$body = @{
    clientId='CLI-001'; deliveringFirmId='FIRM-SUMMIT'; receivingFirmId='FIRM-NORTHSTAR'
    sourceAccountId='ACC-SRC-001'; destinationAccountId='ACC-DST-001'; transferType='FULL'
} | ConvertTo-Json
$creationHeaders = @{ 'X-API-Key'=$apiKey; 'Idempotency-Key'=[guid]::NewGuid().ToString('N') }
$created = Invoke-RestMethod -Method Post "$baseUrl/api/transfers" `
    -Headers $creationHeaders -ContentType 'application/json' -Body $body
$beforeTransfer = $created | ConvertTo-Json -Depth 20 -Compress
$document = $documents.items | Where-Object documentStatus -eq 'READY' | Select-Object -First 1
# Run from the repository root with the local .venv available.
$dataDir = & .\.venv\Scripts\python.exe -c "from backend.core.config import Settings; print(Settings.from_environment().data_dir)"
$checkDir = Join-Path $dataDir 'verification/render'
New-Item -ItemType Directory -Force $checkDir | Out-Null
$beforeFile = Join-Path $checkDir 'before.pdf'
$downloadUrl = "$baseUrl/api/documents/$($document.documentId)/download"
Invoke-WebRequest -UseBasicParsing $downloadUrl -Headers $headers -OutFile $beforeFile
$beforeHash = (Get-FileHash $beforeFile -Algorithm SHA256).Hash
```

Use **Manual Deploy → Deploy latest commit** on the same Render service, retaining the same disk. After readiness returns, in that same PowerShell session run:

```powershell
Invoke-RestMethod "$baseUrl/health"
$after = Invoke-RestMethod "$baseUrl/api/transfers/$($created.transferId)" -Headers $headers
if (($after | ConvertTo-Json -Depth 20 -Compress) -ne $beforeTransfer) { throw 'Transfer was lost or changed' }
$afterRun = Invoke-RestMethod "$baseUrl/api/transfers/TRF-1002/reconciliation" -Headers $headers
if ($afterRun.reconciliationRunId -ne $run.reconciliationRunId) { throw 'Reconciliation history changed' }
$afterFile = Join-Path $checkDir 'after.pdf'
Invoke-WebRequest -UseBasicParsing $downloadUrl -Headers $headers -OutFile $afterFile
if ((Get-FileHash $afterFile -Algorithm SHA256).Hash -ne $beforeHash) { throw 'PDF bytes changed' }
if ($beforeHash.ToLowerInvariant() -ne $document.checksumSha256) { throw 'PDF checksum mismatch' }
'Persistence checks passed'
$headers.Clear(); $creationHeaders.Clear(); Remove-Variable apiKey, secret
```

Keep coordinated backups of SQLite and immutable PDFs. Do not copy just a live `.db` while WAL writes are active or delete the disk to fix a failed deploy. Restore procedures must recover document bytes and database metadata together. Local development data, an existing Railway volume, and a Render disk are separate stores; switching hosting does not migrate existing data automatically.

## Troubleshooting and verification record

| Symptom | Check |
|---|---|
| `No module named backend` | Root Directory must be blank; use `python -m backend.start`. |
| Requirements file not found | Build Command must be `python -m pip install -r backend/requirements.txt` from the repository root. |
| `startup_failed`, phase `configuration` | Check APP_ENV=production, nonblank API_KEY, DATA_DIR=/data, and actual disk attachment. No Railway mount variables are required. |
| Failure during `storage` | Check disk capacity, write permissions, mount path and filesystem support. No fallback storage is used. |
| Failure during `schema` | Preserve disk, inspect version/migrations, restore a coordinated backup if needed. Never reset/drop tables as a workaround. |
| Failure during `demo_documents` | Restore the recorded sample bytes with the expected checksum; do not replace document references to hide corruption. |
| Health failure / no open port | Read startup logs; verify `PORT` and the exact launcher. Initialization failure prevents readiness. |
| 401 on protected APIs | Supply the configured secret in `X-API-Key`; use Swagger Authorize. |
| TRF-1002 missing | Set SEED_DEMO_DATA=1 and deploy with the existing disk. |
| Database locked / 503 | Keep one worker/instance; avoid concurrent manual seeding and requests. Retry with the same idempotency key where supported. |

Local verification command: `.\.venv\Scripts\python.exe -m pytest -q`. Tests use isolated temporary databases. The existing real-HTTP subprocess tests execute `python -m backend.start`, seed all five transfers, upload/download a PDF, reconcile, restart, and verify persisted IDs and bytes. Render disk detection tests use an explicitly mocked mount, not a live Render disk. Cloud build, health routing, disk mount, redeployment and backup restore remain manual acceptance checks.

Executed on 2026-11-01 using the existing Windows virtual environment, Python 3.13.14:

- Full suite: **252 passed, 0 failed in 70.41 seconds**, including nine Render-specific checks. One existing upstream Starlette TestClient deprecation warning.
- `.\.venv\Scripts\python.exe -m pip check`: exit 0, no broken requirements.
- All three PowerShell command blocks in this guide parsed without syntax errors.
- Existing tests also passed for database creation, transactional migration failure, foreign keys/WAL, idempotent seeding, authentication and real HTTP startup/restart persistence.

Created `docs/RENDER_DEPLOYMENT.md` and `tests/test_render_deployment.py`. Updated `backend/core/runtime.py`, `backend/core/config.py`, the `backend/start.py` description, `.env.example`, `AGENTS.md`, `README.md`, `ARCHITECTURE.md`, and `PROJECT_PLAN.md`. No dependencies, models, migration definitions, seed algorithms, business APIs or financial calculations were changed. No cloud service was created or deployed.
