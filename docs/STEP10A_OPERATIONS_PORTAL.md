# Step 10A — TransferIQ Operations Portal

## Delivered scope

The portal is a read-only React/TypeScript single-page application under `frontend/`. It uses Vite, React Router, Tailwind's Vite integration, Zod runtime response validation, and a typed GET-only API client. FastAPI serves the compiled application at `/portal` and its immutable build assets at `/portal/assets` when `frontend/dist` exists.

The application contains:

- an operations dashboard for the five allowlisted fictional transfer scenarios;
- transfer overview and custody-boundary notices;
- backend-derived reconciliation positions, classifications, and exception evidence;
- an AI investigation view that shows persisted plan context only when a real run and plan are supplied;
- read-only plan verification and append-only audit events;
- run-scoped fictional document metadata and PDF links;
- loading, malformed-response, network, 404, rate-limit, and empty states;
- desktop and mobile layouts with keyboard-accessible native controls.

It contains no workflow trigger, approval, rejection, financial correction, settlement, upload, or private API operation. Human decisions remain in UiPath Maestro. IXP remains disabled by default and no Flow, agent, or IXP artifact was changed.

## API contracts used

The production OpenAPI document was inspected before implementation. The portal calls only these existing public GET routes:

| Purpose | Route |
|---|---|
| Scenario inventory/detail | `/api/demo/transfers`, `/api/demo/transfers/{transferId}` |
| Existing run transfer | `/api/demo/runs/{runId}/transfer` |
| Delivering positions | `/api/demo/runs/{runId}/delivering/accounts/{accountId}/positions` |
| Receiving transfer staging | `/api/demo/runs/{runId}/receiving/accounts/{accountId}/positions` |
| Reconciliation/exceptions | `/api/demo/runs/{runId}/reconciliation`, `/api/demo/runs/{runId}/exceptions` |
| Investigation references | `/api/demo/runs/{runId}/investigation-references` |
| Documents | `/api/demo/runs/{runId}/documents`, `/api/demo/runs/{runId}/documents/{documentId}/download` |
| Resolution plan | `/api/demo/runs/{runId}/resolution-plans/{planId}` |
| Verification/audit | `/api/demo/runs/{runId}/resolution-plans/{planId}/verify`, `/api/demo/runs/{runId}/resolution-plans/{planId}/audit` |

The existing catalog contract was extended with display-only fictional metadata: client and firm names, fictional source/destination account references, transfer type/status, and fixture timestamp. `/api/demo/transfers` remains a packaged precomputed fixture and never opens the private database. The generator and regression test were updated together.

No public API currently discovers runs or plans for a transfer, lists review history across runs, or returns the complete durable Autonomous Agent output. The portal therefore does not invent those values. An operator may optionally enter already-known public `runId` and `planId` values; without them, the relevant pages display explicit unavailable/empty states. “Reviewed cases” is shown as unavailable rather than calculated.

## Local development and verification

```powershell
# Backend, repository root
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Frontend, second terminal
npm ci --prefix frontend
npm run dev --prefix frontend
# Open http://127.0.0.1:5173/portal/

# Frontend checks
npm test --prefix frontend
npm run build --prefix frontend

# Backend regressions
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

The development server proxies `/api` to `http://127.0.0.1:8000` by default. Override only for development with `VITE_API_PROXY_TARGET`. Production uses same-origin relative URLs; no backend secret is compiled into the browser bundle.

## Render deployment

Keep the existing Python web service, persistent `/data` disk, health check, environment variables, and start command. Change only the Build Command to:

```text
npm ci --prefix frontend && npm run build --prefix frontend && python -m pip install -r backend/requirements.txt
```

Keep the Start Command:

```text
python -m backend.start
```

After the user deploys the reviewed revision, verify `/health`, `/api/demo/transfers`, `/portal`, a deep link such as `/portal/transfers/TRF-1002/reconciliation`, `/docs`, and `/openapi.json`. The portal build is intentionally not committed; it is produced during deployment. No deployment is performed or claimed by this implementation.

## Acceptance boundaries

- Reconciliation values are displayed, never recalculated in the browser.
- SEC-103's fixture evidence remains corporate action `CA-2026-081`; SEC-104 remains an unresolved `-20` difference.
- Original custody positions and receiving staging records remain unchanged.
- Missing durable contracts remain visible as unavailable states, not fabricated activity.
- The existing Step 9 approval/rejection and Step 8 agent behavior are not modified.

## Executed verification — 2026-11-09

| Check | Actual result |
|---|---|
| `npm test` in `frontend/` | **2 files, 8 tests passed**, 5.07 seconds |
| `npm run build` in `frontend/` | **Success**; 2,162 modules transformed; HTML 0.54 kB, CSS 15.69 kB, JS 381.80 kB before gzip |
| `npm audit --omit=dev` | **0 vulnerabilities** |
| Focused backend portal/catalog tests | **40 passed**, one existing Starlette/httpx deprecation warning, 6.85 seconds |
| `python -m pytest -q --tb=short` | **461 passed**, same existing warning, 133.24 seconds |
| Local same-origin HTTP integration | `/portal`, deep-link fallback, compiled asset, `/api/demo/transfers`, `/health`, and `/docs` returned 200; POST `/portal` returned 405 |
| Browser rendering | Headless installed Chrome rendered the dashboard and TRF-1002 reconciliation at 1440×1000; 390×844 mobile body width equaled viewport width (no page overflow) |

Bounded production reads against `https://transferiq-api.onrender.com` returned:

- `/health`: **200**, `status=ok`, `database=ok`, `fictionalDemo=true`;
- `/api/demo/transfers`: **200**, five items;
- `/openapi.json`: **200**, 21 `/api/demo/*` paths;
- `/portal`: **404**.

The production catalog did **not** yet include `clientName`, proving that this Step 10A revision is not deployed. No Render deployment or production portal success is claimed. Deployment and post-deployment `/portal` verification remain the next actions.

Files added or materially changed for Step 10A: `frontend/`, `backend/main.py`, `backend/schemas/judging.py`, `backend/resources/judging_samples.json`, `scripts/build_judging_samples.py`, `tests/test_judging.py`, `tests/test_step10_portal.py`, and the status/deployment documentation. No Maestro, agent, IXP, migration, financial rule, resolution write API, or custody model file was changed.
