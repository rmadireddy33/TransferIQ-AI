# Deterministic reconciliation (Step 3)

The engine compares fictional delivering custody snapshots with receiving transfer staging. It runs entirely in Python, independently of AI. It never changes quantities, creates settlement records, or advances the transfer lifecycle. A completed calculation is not a completed securities transfer.

## Database migration and input selection

Schema version 2 adds `corporate_actions`, `security_identifier_mappings`, `cost_basis_records`, `reconciliation_runs`, and `transfer_exceptions`. Foreign keys link evidence to securities/transfers and exceptions to the matching run/transfer pair. A unique `(transfer_id, input_fingerprint)` constraint prevents duplicate run results for identical inputs. All quantities and basis amounts use exact Decimal-backed text storage; timestamps remain UTC.

The v1-to-v2 migration runs inside a transaction. It adds nullable `observed_identifier` to source snapshots and nullable `snapshot_date` and `observed_identifier` to staging. Existing values, original snapshot triggers, staging uniqueness constraints, and audit history are preserved. Existing null snapshot dates are not replaced with assumed dates derived from `createdAt`. Adding columns follows [SQLite's supported ALTER TABLE mechanism](https://www.sqlite.org/lang_altertable.html).

The migration is applied on startup or with `python -m backend.database.init_db`. Fresh databases create the current schema directly. Unknown versions, unexpected partial schemas, or inconsistent foreign keys fail rather than resetting data. Stop older application processes before upgrading. A consistent backup of the development database was taken before this upgrade; see STEP3_VERIFICATION.md.

The source scope is one account and one date: by default, the latest stored source snapshot date. An optional `sourceSnapshotDate` in the reconcile request selects an exact stored date. The receiving scope is all staging rows for that transfer, with each row's observed date. Missing source snapshots return 422. PARTIAL transfers return 422 until a supported asset-selection contract exists; the engine must not compare an entire source account against an unspecified partial transfer.

The security master has a unique canonical identifier. Its security ID is therefore the canonical grouping key. An absent observed identifier means the existing master reference supplied by Step 2; a supplied differing identifier must pass verified mapping checks. Symbols are never used for identity matching.

## Rules and classifications

| Condition | Classification / outcome |
|---|---|
| Same canonical identity, equal comparable quantities, no evidence transformation needed | Position `MATCHED`; no position exception |
| Comparable quantity differs | `QUANTITY_MISMATCH`, `UNRESOLVED`; difference is receiving minus expected |
| Verified split explains the quantity | `CORPORATE_ACTION_TIMING`, `EXPLAINED`; original and normalized quantities retained |
| Verified effective identifier change establishes identity and quantity matches | `SECURITY_IDENTIFIER_CHANGE`, `EXPLAINED` |
| Identifier evidence absent, unverified, conflicting, wrong canonical security, or date-invalid | `SECURITY_IDENTIFIER_CHANGE`, `REQUIRES_INVESTIGATION` |
| Only source position exists | `MISSING_SECURITY`, `UNRESOLVED` |
| Only receiving position exists | `EXTRA_SECURITY`, `UNRESOLVED` |
| Multiple input rows for one canonical security | `DUPLICATE_POSITION`, `UNRESOLVED`; no automatic aggregation |
| Unsupported/ambiguous action, unsupported staging status, insufficient timing, or unsupported precision | `REQUIRES_INVESTIGATION`, `UNRESOLVED` |
| No basis lots or incomplete quantity, amount, date, status, or evidence | `COST_BASIS_MISSING`, `UNRESOLVED`, separate from position counts |
| Basis lot quantities disagree with staging, acquisition dates are later than the target date, or duplicate lot evidence is present | `COST_BASIS_INCONSISTENT`, `UNRESOLVED`, separate from position counts |

Corporate actions require a verified record, a nonblank evidence reference, a supported SPLIT/REVERSE_SPLIT type, and positive integer numerator/denominator. The effective-date interval is `(earlier snapshot date, later snapshot date]`. Multiple distinct actions on distinct dates compose once in date order; reverse-time comparison uses inverse ratios. Repeated action evidence or multiple actions on the same effective date are treated as ambiguous, never silently deduplicated or multiplied twice. A source snapshot on or after an action date is already on that side of the event and does not receive that action again.

Normalization uses a local Decimal context of precision 80 with inexact operations trapped. Results must fit 18 integer and 8 fractional digits. Nonterminating fractional results, overflow, or a need for rounding remain unresolved; no cash-in-lieu or rounding policy is invented. If known corporate-action records exist but a comparison date is missing, even raw equality cannot establish a timing-safe match. Legacy rows with no known actions can still match by raw canonical identity and exact quantity without assuming any date.

Identifier changes support one verified forward mapping from the observed old identifier to the master canonical identifier, for the same canonical security, with `source date < effective date <= target date`. Multiple effective verified candidates are ambiguous. Reverse/chained identifier changes remain unsupported and require investigation.

The existing unique `(transfer_id, security_id)` database constraint rejects duplicate persisted staging rows. The comparison service also detects duplicate rows defensively before matching, including duplicate source streams. Tests exercise both the database rejection and duplicate staging input to the pure comparison service. No constraint is weakened to admit bad demo data.

Cost-basis lots are checked independently. All lots must be complete, evidence-backed, and their Decimal quantities must sum to the receiving staging quantity. A documented zero basis is valid; a null amount is missing. The engine does not infer a correct market value or acquisition cost. `costBasisIssues` is separate from the quantity-position counters, and a basis exception does not change the quantity result or claim settlement failure.

## Result contract and history

All new endpoints require the existing `X-API-Key` credential, including reads of exceptions, runs, and reference evidence. A missing/wrong key returns 401 when configured; missing server configuration returns 503. Existing public Step 2 demonstration GET routes retain their behavior. Resource-level user roles remain a later phase; this API key authorizes the local demo service principal.

| Method | Endpoint | Response |
|---|---|---|
| POST | `/api/transfers/{transferId}/reconcile` | 201 new run or 200 reused run; optional body `{ "sourceSnapshotDate": "2026-08-01" }` or `{}`/no body |
| GET | `/api/transfers/{transferId}/reconciliation` | Last explicitly requested completed run; 404 if none |
| GET | `/api/transfers/{transferId}/exceptions` | Paginated findings for that run only, including explained findings |
| GET | `/api/reconciliation-runs/{runId}` | Historical run with its original findings |
| GET | `/api/corporate-actions` | Paginated reference records, including verification flags |
| GET | `/api/securities/{securityId}/corporate-actions` | Paginated actions for the security |
| GET | `/api/securities/{securityId}/identifier-mappings` | Paginated mappings for the canonical security |

List pagination follows Step 2's `items`, `total`, `limit`, and `offset` contract. Domain errors contain `detail.code` and `detail.message`; schema errors use FastAPI's 422 validation details. Database conflicts roll back the entire operation and return 409; lock/unavailability failures return 503 and may be retried. Reconciliation is synchronous and bounded to the local demo workload; no fabricated running-job response is returned.

The response includes run/transfer IDs, execution status, business comparison status, source/target snapshot hashes, full input fingerprint, rule version, observed dates, UTC times, summary, position results, and findings. Decimal quantities serialize as strings. `expectedQuantity` and `normalizedQuantity` are aliases for the same comparison quantity; null means a defensible expected quantity could not be established. Missing positions use null for the absent side, not an invented zero.

`executionStatus=COMPLETED` means calculation and persistence succeeded. `status=RECONCILED` means there are no unresolved position or cost-basis issues; explained findings may still exist. Otherwise it is `EXCEPTIONS_DETECTED`. These statuses do not update `Transfer.status`.

Position accounting satisfies:

```text
totalPositions = directlyMatched + evidenceExplained + unresolved
```

`costBasisIssues` is counted separately. Thus TRF-1004 has seven direct matches, zero unresolved quantity positions, and one cost-basis issue.

The fingerprint includes selected source rows, staging quantities/versions/dates, relevant security-master records, candidate mappings (including conflicts), actions (including verification/evidence), basis records, transfer context, and rule version. All are read within one SQLite transaction and saved as an input snapshot with the result. Identical input reuses the completed run and exception IDs; `lastRequestedAt` is refreshed. Changed input creates a new run without rewriting earlier evidence/results. New calculation, findings, and audit event commit together. Concurrent conflicts can be retried safely with the same request; the unique fingerprint constraint prevents duplicate completed results.

The transfer-level exceptions endpoint returns only the last explicitly requested run's findings, so historical unresolved findings are not mixed into the active view. GET does not recompute after data changes: POST reconciliation again before treating a result as current. Historical runs remain accessible by run ID. Replaying older inputs can select that existing result again without creating another exception set.

## Fictional demonstration scenarios

The seed CLI now inserts all five scenarios, preserving TRF-1001 and every existing record. `seed_demo(factory)` retains its original narrow Step 2 fixture behavior for regression tests; `include_scenarios=True` and the CLI add Step 3 fixtures. Each new scenario has a dedicated source/destination account, avoiding changes to TRF-1001's source scope.

| Transfer | Scenario | Positions | Direct | Explained | Unresolved quantity | Basis issues |
|---|---|---:|---:|---:|---:|---:|
| TRF-1001 | CLEAN_TRANSFER | 7 | 7 | 0 | 0 | 0 |
| TRF-1002 | CORPORATE_ACTION_AND_SHORTAGE | 7 | 5 | 1 | 1 | 0 |
| TRF-1003 | SECURITY_IDENTIFIER_CHANGE | 1 | 0 | 1 | 0 | 0 |
| TRF-1004 | COST_BASIS_MISSING | 7 | 7 | 0 | 0 | 1 |
| TRF-1005 | UNSUPPORTED_CORRECTION | 1 | 0 | 0 | 1 | 0 |

TRF-1002 uses SEC-101 through SEC-107. SEC-103 has 40 source shares dated 2026-08-01 and 80 staging shares dated 2026-08-15; verified evidence CA-2026-081 records a 2-for-1 split on 2026-08-10. SEC-104 has 120 source shares versus 100 staging shares and stays unresolved at 100. TRF-1003 uses SEC-201 with fictional old/new observations and MAP-2026-201. TRF-1004 lacks the SEC-007 basis record. TRF-1005 compares 120 with 100 for SEC-301 without supporting correction evidence. Reference verification flags represent independent **synthetic reference fixtures**, not a claim that any live provider was queried.

## Run, test, and inspect in Swagger

From the repository root, with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m backend.database.init_db
.\.venv\Scripts\python.exe -m backend.database.seed
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\start-backend.ps1
```

Configure `API_KEY` in the ignored `.env` or the server environment before startup. In Swagger at <http://127.0.0.1:8000/docs>, click **Authorize**, enter the configured key, then use **Reconciliation** -> POST `/api/transfers/{transferId}/reconcile` with `TRF-1002` and `{}`. The result is read from stored records, not hardcoded per transfer. Use the GET reconciliation/exceptions/run routes to inspect persisted output.

In a second PowerShell terminal, load the same key without printing it (the application loader respects process environment over `.env`):

```powershell
Set-Location C:\Projects\TransferIQ-AI
$env:API_KEY = & .\.venv\Scripts\python.exe -c "from backend.core.config import Settings; print(Settings.from_environment().api_key.get_secret_value())"
.\scripts\verify-reconciliation.ps1
$headers = @{ 'X-API-Key' = $env:API_KEY }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/transfers/TRF-1002/reconcile `
    -Headers $headers -ContentType 'application/json' -Body '{}'
Invoke-RestMethod http://127.0.0.1:8000/api/transfers/TRF-1002/exceptions -Headers $headers
```

The assignment captures the key directly; do not run the embedded Python command alone or share the value. If using a server-only process environment key, provide that same value securely in the second terminal instead. Tests use temporary SQLite databases. The HTTP verification script intentionally persists demo reconciliation runs in the running server's database and checks repeatability and source/staging immutability.

## Future Maestro consumption

Maestro HTTP Request nodes can later call the POST route with `transferId`, then branch on the returned status/summary and consume structured evidence references and exceptions. Decimal strings, stable IDs, explicit statuses, pagination, and persisted fingerprints form the integration contract. The service key belongs in managed credentials, never workflow source. On transient failures, repeat the same POST; on missing records/invalid scope, surface the domain error for investigation. No Maestro Flow, IXP, AI agent, approval UI, automatic correction, document pipeline, or cloud deployment is implemented here.
