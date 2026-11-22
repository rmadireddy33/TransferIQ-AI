# TransferIQ AI Render deployment

Current production host: https://transferiq-api.onrender.com  
Current architecture: one Render Python Web Service, one persistent /data disk, one instance, one Uvicorn worker.

This is the current operating guide. It does not authorize a deployment during documentation or audit work.

## Service settings

| Render field | Value |
|---|---|
| Root Directory | Leave blank |
| Runtime | Python 3 |
| Build Command | npm ci --prefix frontend && npm run build --prefix frontend && python -m pip install -r backend/requirements.txt |
| Start Command | python -m backend.start |
| Pre-Deploy Command | Leave blank |
| Instance count | 1 |
| Persistent disk mount | /data |
| Health Check Path | /health |

The launcher imports backend.main:app, binds 0.0.0.0 to Render's PORT, and forces one worker. Database initialization and migrations run at application startup, when the persistent disk is mounted, never during build.

## Required application settings

Store all real values only in Render environment settings. Do not use VITE-prefixed secrets.

    APP_ENV=production
    DATA_DIR=/data
    API_KEY=<strong private API secret>
    SEED_DEMO_DATA=1
    SQLITE_BUSY_TIMEOUT_MS=5000
    MAX_DOCUMENT_BYTES=10485760
    PYTHONDONTWRITEBYTECODE=1
    PYTHONUNBUFFERED=1

    PUBLIC_DEMO_ENABLED=1
    PUBLIC_DEMO_REQUESTS_PER_MINUTE=60
    PUBLIC_DEMO_GLOBAL_REQUESTS_PER_MINUTE=300
    DEMO_EXECUTION_ENABLED=1
    DEMO_MAX_RUNS=50
    DEMO_RUN_TTL_HOURS=24
    DEMO_STORAGE_LIMIT_MB=128

Render supplies PORT. Do not configure DATABASE_URL: SQLite is the only supported database.

## Controlled portal investigation settings

The public portal can remain readable when controlled starts are disabled. Enable starts only after every secret and the active UiPath webhook are configured.

    PORTAL_INVESTIGATION_ENABLED=1
    PORTAL_OPERATOR_ID=demo-operator
    PORTAL_OPERATOR_ACCESS_KEY=<at least 16 random characters>
    SESSION_SECRET=<at least 32 random characters>
    PORTAL_SESSION_TTL_MINUTES=60
    PORTAL_USER_MAX_ACTIVE=1
    PORTAL_GLOBAL_MAX_ACTIVE=3
    PORTAL_STARTS_PER_MINUTE=2
    PORTAL_WORKFLOW_TIMEOUT_MINUTES=<5 through 240>
    UIPATH_WEBHOOK_URL=<active Integration Service webhook URL>
    UIPATH_WEBHOOK_AUTH_HEADER_NAME=X-TransferIQ-Webhook-Key
    UIPATH_WEBHOOK_AUTH_HEADER_VALUE=<at least 16 random characters>
    UIPATH_WEBHOOK_TIMEOUT_SECONDS=15

The code default for PORTAL_INVESTIGATION_ENABLED is 0 and startup fails closed if it is set to 1 with incomplete portal/webhook secrets. The configured server workflow timeout is independent of the browser's bounded polling window. A test environment may use 10 minutes; production owners should choose an operationally appropriate value within the validated 5-240 minute range.

Never expose the webhook URL/header value, operator access code, session secret, private API key, review capability, or signed attachment URL in the frontend, logs, screenshots, or documentation.

## Durable storage

    /data/transferiq.db                  private application SQLite, schema v4
    /data/documents/                     private document bytes
    /data/staging/ and /data/tmp/        bounded document writes
    /data/competition/transferiq.db      demo-run registry, schema v2
    /data/competition/runs/...           isolated synthetic runs and PDFs
    /data/portal/transferiq.db           portal tracking registry, schema v3

Startup validates the mount before creating state, migrates supported schemas transactionally, recovers pending document writes, and optionally adds missing fictional fixtures. It does not reset existing databases. Only files below /data survive an instance replacement.

Back up SQLite and document bytes together. Do not copy only a live database file while WAL writes are active, delete the disk to repair a release, or scale this SQLite service to multiple instances/workers.

## UiPath handoff

Render does not deploy the UiPath solution. The target UiPath tenant must already have:

- active solution 1.1.1 or a separately validated later version;
- an enabled authenticated HTTP Webhook connection;
- a deployed PortalWebhook trigger and issued URL;
- an eligible single-user Quick Form reviewer;
- Autonomous Agent and Analyze Files availability;
- the TransferIQ_Document_Retrieval API Workflow.

After a new target-tenant deployment, copy only the issued webhook URL and matching authentication value into Render secrets, then enable portal investigations. Do not commit tenant bindings.

## Bounded verification

Public checks:

    Invoke-RestMethod https://YOUR-SERVICE.onrender.com/health
    Invoke-RestMethod https://YOUR-SERVICE.onrender.com/api/demo/transfers
    (Invoke-WebRequest https://YOUR-SERVICE.onrender.com/portal -UseBasicParsing).StatusCode
    (Invoke-WebRequest https://YOUR-SERVICE.onrender.com/openapi.json -UseBasicParsing).StatusCode

Expected: HTTP 200 and five fictional catalog entries. Verify a protected private route without X-API-Key returns 401.

Before any live workflow start:

1. GET /api/portal/session and confirm enabled=true.
2. Authenticate through the portal with the owner-supplied access code.
3. Start one allowlisted scenario once and record its PEX ID.
4. Confirm webhook acceptance yields TRIGGERED, not COMPLETED.
5. Follow the persisted tracking page through agent/human/verification state.
6. Confirm final audit and unchanged-position results.

Do not repeatedly retry an uncertain webhook delivery. The backend intentionally makes one bounded attempt.

## Local deployment regression commands

    & .\.venv\Scripts\python.exe -m pytest -q --tb=short
    & .\.venv\Scripts\python.exe -m pip check
    npm test --prefix frontend -- --run
    npm run build --prefix frontend

The latest audited results are 479 backend tests and 22 frontend tests passed. The frontend production build also succeeded. These results include the portal presentation cleanup and registry v2-to-v3 migration coverage.

## Troubleshooting

| Symptom | Check |
|---|---|
| No module named backend | Root Directory must be blank; start with python -m backend.start. |
| Frontend missing | Use the combined npm build and Python dependency command exactly. |
| Startup fails in configuration | Check APP_ENV, API_KEY, DATA_DIR, portal flag, and every required portal/webhook secret. |
| Startup fails in storage | Confirm the persistent disk is attached at /data and writable. |
| Startup fails in schema | Preserve the disk and inspect supported migrations; never reset as a workaround. |
| 401 on private API | Supply the configured X-API-Key. |
| 401/403 from webhook | Verify the Integration Service header name/value match Render secrets. |
| Active investigation blocks another | Read the existing PEX state or wait for the configured server deadline; browser refresh does not create a new run. |
| Database locked | Keep one instance and one worker; avoid concurrent maintenance. |

Railway configuration remains an undeployed alternative described in [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md). It is not the current production platform.
