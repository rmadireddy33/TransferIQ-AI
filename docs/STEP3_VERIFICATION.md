# Step 3 verification

Completed across the 2026-10-31 / 2026-11-01 local session (America/New_York), using the existing Python 3.13 virtual environment. No additional dependencies were installed.

## Automated test results

The unmodified Step 2 baseline passed: **68 passed**, one upstream Starlette/httpx TestClient deprecation warning. After the schema/API additions, the same 68 regression tests passed again (the schema-version assertion now uses the current version constant).

The first expanded run reported **114 passed, 3 failed**. The failed assertions changed staging quantities but assumed no additional cost-basis findings. The engine correctly emitted inconsistent-basis findings, which changed ordering/counts. The assertions were corrected to select the intended finding by type and include the separate basis issue. No financial discrepancy was suppressed to make tests pass.

After migration coverage and stricter insufficient-date checks, executed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Final observed result:

```text
120 passed, 1 warning in 14.67s
```

The warning remains the upstream Starlette/httpx deprecation; it is not suppressed. Tests use isolated temporary SQLite databases. New checks cover all five scenarios, action date boundaries/verification, ambiguous and repeated actions, forward and reverse quantity comparison, valid/invalid/ambiguous identifier mapping, missing/extra/duplicate positions, separate missing/inconsistent basis, unsupported correction, exact Decimal precision, nonterminating splits, authentication, invalid IDs, stable repeated runs, changed evidence/versions, historical results, restart persistence, transaction rollback, and populated v1 migration/failed-migration rollback. No Pytest test reads or writes the development database.

## Development migration and seed

Before migration, the old backend process was stopped. SQLite's backup API created a consistent backup at:

```text
data/backups/pre-step3-20261101T035907087833Z.db
```

The filename uses UTC. The migration and seed were invoked through the same functions used by the initialization and seed CLIs. Observed:

```text
Migration applied from schema 1 to schema 2
Extended seed inserted: 81
Repeated seed inserted: 0
PASS: every original row/value preserved across migration and seed; foreign keys valid.
```

Preservation was checked by capturing every original table's columns and rows, then comparing those exact original values after migration and seeding. New columns were nullable, not backfilled with invented values. Original TRF-1001 source/staging records were retained. A foreign-key check returned no violations. The backup and active database are both under ignored `data/`.

## Real HTTP checks

A temporary Uvicorn listener at `127.0.0.1:8001` used a randomly generated, process-only key for authenticated verification. It was stopped afterward. Ran both:

```powershell
.\scripts\verify-backend.ps1 -BaseUrl http://127.0.0.1:8001
.\scripts\verify-reconciliation.ps1 -BaseUrl http://127.0.0.1:8001
```

All 14 existing HTTP GET checks passed, including Swagger and OpenAPI. Actual authenticated POSTs and GETs produced:

| Transfer | Total | Direct | Explained | Unresolved quantity | Basis issues |
|---|---:|---:|---:|---:|---:|
| TRF-1001 | 7 | 7 | 0 | 0 | 0 |
| TRF-1002 | 7 | 5 | 1 | 1 | 0 |
| TRF-1003 | 1 | 0 | 1 | 0 | 0 |
| TRF-1004 | 7 | 7 | 0 | 0 | 1 |
| TRF-1005 | 1 | 0 | 0 | 1 | 0 |

Each POST was repeated. The same run ID and exception IDs were reused, exception counts stayed stable, and source/staging HTTP representations remained identical before and after. Latest-run, historical-run, and exception-list reads agreed. All three reference-data routes returned HTTP 200. SEC-104 remained at 100 staging shares; no correction or settlement occurred.

The updated backend was then started through `scripts/start-backend.ps1 -NoReload` at **http://127.0.0.1:8000**. No local API key had been configured, so a random key was generated in the ignored `.env` without displaying it. All five authenticated scenario checks passed again on port 8000, and `/docs` returned HTTP 200. This server was left running for Swagger access. Use the local `.env` key in Swagger's Authorize dialog; do not share or commit it.

## Files added

```text
backend/api/reconciliation.py
backend/database/seed_reconciliation.py
backend/models/reconciliation.py
backend/schemas/reconciliation.py
backend/services/reconciliation.py
backend/services/reconciliation_rules.py
tests/test_reconciliation.py
tests/test_migrations.py
scripts/verify-reconciliation.ps1
docs/RECONCILIATION.md
docs/STEP3_VERIFICATION.md
```

Modified: `backend/main.py`, `backend/api/dependencies.py`, `backend/database/migrations.py`, `backend/database/seed.py`, `backend/models/entities.py`, `backend/schemas/contracts.py`, the schema-version assertion in `tests/test_database.py`, `README.md`, `ARCHITECTURE.md`, `PROJECT_PLAN.md`, and `AGENTS.md`. Local runtime changes: `.env`, SQLite database, and pre-migration backup. No Git commit was created; the workspace has no Git repository initialized.

## Reproduce

See [RECONCILIATION.md](RECONCILIATION.md) for exact PowerShell commands, all seven new endpoints, rules, authentication, and Swagger steps. The live verification script persists runs in the server database; Pytest remains isolated. GET returns the last explicitly requested run and does not automatically recompute after data edits; POST again to establish a current comparison.

No Maestro Flow, IXP, AI agent, PDF/document pipeline, frontend, human approval form, automatic financial correction, or cloud deployment was implemented or claimed tested.
