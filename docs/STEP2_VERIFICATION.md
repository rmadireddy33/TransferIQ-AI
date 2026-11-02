# Step 2 executed verification

Verified on 2026-10-31 in `C:\Projects\TransferIQ-AI`, Windows PowerShell, Python 3.13.14. These are observed results, not planned checks.

## Environment and dependency installation

`py -3.13 -m venv .venv` completed successfully. The generic Windows Store `python` alias and sandboxed virtual-environment launcher initially failed with a file-access error. Running the project interpreter outside the restricted tool sandbox resolved execution; no global installation or alternate database was used.

Executed `.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt` successfully. Installed direct dependencies:

| Dependency | Observed version |
|---|---|
| FastAPI | 0.162.0 |
| SQLAlchemy | 2.0.55 |
| Pydantic | 2.14.2 |
| Uvicorn | 0.54.0 |
| python-dotenv | 1.2.4 |
| Pytest | 9.2.0 |
| httpx | 0.28.1 |

`.\.venv\Scripts\python.exe -m pip check` returned `No broken requirements found.` The manifest uses bounded compatible ranges, not a full dependency lockfile.

## Automated tests

Executed `.\.venv\Scripts\python.exe -m pytest -q` after implementation: initially 65 passed. After adding replacement-insert immutability guards and regression tests, the final run reported:

```text
68 passed, 1 warning in 5.52s
```

The warning is an upstream `StarletteDeprecationWarning` about using httpx with Starlette TestClient; it was not suppressed. All tests use temporary directories and explicitly supplied settings. No Pytest test used `data/transferiq.db`.

Coverage includes database creation, WAL/foreign-key/busy-timeout settings, persistence and idempotency across application restart, foreign keys and composite account ownership, API reads, transfer creation, validation and authorization failures, pagination, rollback, UTC timestamps, Decimal precision, unique staging rows, state-transition guards, idempotent seeding that preserves changes, and immutable snapshots/audit events. Direct SQL replacement attempts are tested as well as ordinary updates/deletes. Unsupported or unversioned existing databases are rejected without reset.

## Persistent development database

Executed, in order:

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db
.\.venv\Scripts\python.exe -m backend.database.seed
.\.venv\Scripts\python.exe -m backend.database.seed
```

Observed:

```text
SQLite initialized without resetting data: C:\Projects\TransferIQ-AI\data\transferiq.db
Fictional demonstration seed complete: 31 rows inserted; existing records preserved.
Fictional demonstration seed complete: 0 rows inserted; existing records preserved.
```

The seed comprises two firms, two clients, four accounts, seven securities, one transfer, seven immutable source snapshots, seven receiving staging records, and one audit event. No test-created transfers were inserted into the development database.

## Actual HTTP verification

Started Uvicorn through `.\scripts\start-backend.ps1 -NoReload`. The server reported successful application startup and listened at `http://127.0.0.1:8000`.

Ran `.\scripts\verify-backend.ps1` against the live server. All returned HTTP 200:

```text
/health
/api/clients
/api/clients/CLI-001
/api/firms
/api/accounts/ACC-SRC-001
/api/transfers
/api/transfers/TRF-1001
/api/transfers/TRF-1001/assets
/api/delivering/accounts/ACC-SRC-001/positions
/api/receiving/accounts/ACC-DST-001/positions
/api/securities
/api/securities/SEC-001
/docs
/openapi.json
```

The script also confirmed seven matching source/staging quantities and `settledHoldings=false`. The verification server was stopped afterward, and the localhost health endpoint was confirmed no longer listening. The persistent database remains available for the next launch.

Mutation/authentication tests were exercised through FastAPI TestClient against isolated SQLite databases; live development HTTP checks were read-only. No production, Railway, UI, document, reconciliation, approval, or UiPath integration checks were run because those features are out of scope and not implemented.

## Files created or modified

New source and test files (package `__init__.py` files are included in each new package):

```text
backend/__init__.py
backend/main.py
backend/requirements.txt
backend/api/__init__.py
backend/api/dependencies.py
backend/api/routes.py
backend/core/__init__.py
backend/core/config.py
backend/database/__init__.py
backend/database/session.py
backend/database/migrations.py
backend/database/init_db.py
backend/database/seed.py
backend/models/__init__.py
backend/models/entities.py
backend/models/types.py
backend/schemas/__init__.py
backend/schemas/contracts.py
backend/services/__init__.py
backend/services/lifecycle.py
backend/services/transfers.py
tests/conftest.py
tests/test_api.py
tests/test_database.py
scripts/start-backend.ps1
scripts/verify-backend.ps1
pytest.ini
docs/STEP2_VERIFICATION.md
```

Updated: `README.md`, `ARCHITECTURE.md`, `PROJECT_PLAN.md`, `AGENTS.md`, and `.env.example`. Existing `.gitignore` already excludes `.venv`, `.env`, database files, and caches, so it needed no change. Runtime `.venv/`, test caches, and `data/transferiq.db` were created locally and are not source artifacts. The workspace has no `.git` directory; no commit was attempted.
