# TransferIQ AI final release verification

Verification date: **2026-11-22**  
Scope: final competition release audit  
Recommendation: **PASS WITH LIMITATIONS**

## Executive result

The deployed demonstration is operational, its current portal assets exactly
match the freshly built local assets, and the complete backend and frontend
regression suites pass. The editable Maestro source also passes strict checking,
compiles to 81 nodes and 86 edges with UiPath CLI 1.205.0, validates as `Valid`,
and is semantically equivalent to the checked-in canonical graph.

An unqualified PASS is not supported for two reasons:

1. The checked-in canonical `.flow` has 81 nodes and 86 edges but fails a fresh
   standalone product validation because its `RetrieveCorporateActionDocument`
   node lacks the two workflow-level binding rows for the in-solution
   `TransferIQ_Document_Retrieval` resource. The source-built candidate contains
   those rows and validates. The solution dry-run still reports `Valid`, and the
   deployed 1.1.1 path is proven operational, so this is a repository artifact
   and reproduction discrepancy rather than evidence of a production outage.
2. The portal start route documents CSRF as mandatory, but an isolated local
   probe with a webhook test double received HTTP 201 when the signed session
   cookie and idempotency key were present but `X-CSRF-Token` was omitted. The
   cookie is `Secure`, `HttpOnly`, and `SameSite=Strict` in production, which
   mitigates ordinary cross-site browser requests, but the server-side contract
   is not enforced as documented.

No application code, Flow, Agent prompt, Quick Form, financial rule, database
record, deployment, or production workflow was changed during this audit.

## Verification matrix

| Area | Command or evidence | Observed result |
|---|---|---|
| Backend regression | `.\.venv\Scripts\python.exe -m pytest -q --tb=short` | **481 passed**, 0 failed, 0 skipped, 1 known Starlette/httpx deprecation warning, 153.40 seconds |
| Focused portal regression | `.\.venv\Scripts\python.exe -m pytest tests/test_step10b_portal.py -q --tb=short` | **12 passed**, 1 known warning, 6.30 seconds |
| Python integrity | `compileall` and `pip check` | Compile succeeded; **No broken requirements found** |
| Frontend tests | `npm test -- --run` | **30 passed** in 2 files, 0 failed, 6.16 seconds |
| Frontend build | `npm run build` | Success; 2,162 modules, 1.39 seconds |
| npm production audit | `npm audit --omit=dev --json` | **0 vulnerabilities**; 9 production dependencies, 189 total dependency records |
| Python vulnerability lookup | OSV query of the installed environment | 32 installed PyPI packages queried; **0 vulnerability references** |
| Flow source check | `npm run check` in `.flow-sdk` | **0 errors / 0 warnings** |
| Pinned UiPath CLI | local `.flow-sdk` executable | **1.205.0** |
| Source compile | `flow-sdk flow compile` with ignored tenant bindings | **81 nodes / 86 edges** |
| Candidate validation | `uip maestro flow validate` | **Success / Valid** |
| Semantic comparison | `compare-flow-structure.mjs` | `valid: true`; no missing or extra node IDs or edge tuples; Quick Form and Agent input contracts equivalent |
| Checked-in canonical validation | `uip maestro flow validate` | **Failure**: 1 error and 2 warning diagnostics, all caused by missing in-solution API Workflow binding rows |
| Document retrieval workflow | `uip api-workflow validate` | **Success / Valid** |
| Solution dry-run | `uip solution pack ... --dry-run` | **Success / Valid**; known `ImplicitConnection` catalog advisory remains |
| Markdown links | read-only link checker | 44 Markdown files, 87 local links, **0 missing targets** |
| Encoding | UTF-8/mojibake scan of `frontend/src` and `frontend/dist` | 11 files scanned, **0 issues** |

The first sandboxed backend invocation could not start the Windows Store-backed
virtual-environment interpreter. It was not a pytest result. The approved
out-of-sandbox invocation above is the completed regression result.

## Production evidence

### Independently read during this audit

Bounded GET requests only were used. No production POST was made.

| Production check | Result |
|---|---|
| `GET /health` | HTTP 200; `status=ok`, `database=ok` |
| `GET /portal` | HTTP 200 |
| `GET /api/demo/transfers` | HTTP 200; five fictional transfers |
| `GET /api/portal/session` without a cookie | HTTP 200; feature enabled and unauthenticated |
| `GET /api/portal/investigations` without a cookie | HTTP 401 |
| Protected private transfer read without `X-API-Key` | HTTP 401 |
| Production OpenAPI | 51 paths |
| Local versus production OpenAPI | 51 versus 51; no missing or extra paths |

The deployed JavaScript and CSS are byte-identical to the fresh local build:

| Asset | SHA-256 |
|---|---|
| `index-Cr6Ra30d.js` | `9D9506947F4B64B1C0FCBBCD5BAC1A15CB36D4C19FB24C4708FE0E3BBC2F7032` |
| `index-CX0vCK5-.css` | `26C5A4BA0A8088AD8EEE1CDAFCBBC2995F6461B52BDB6AF2251C8EA7175D884E` |

### Owner-supplied authenticated acceptance evidence

Authenticated history could not be independently fetched without using the
operator access code. The owner reported and visually reviewed the following
production state:

- `/data` is the mounted persistent disk;
- the portal registry retains seven investigations;
- TRF-1001 shows one investigation and TRF-1002 shows six;
- approval, rejection, timeout, CLEAN, and open-exception outcomes are visible;
- the PEX detail view and six-stage timeline were visually reviewed;
- UiPath solution 1.1.1 remains deployed.

These observations are accepted as owner-provided production evidence, not
relabelled as independently authenticated API reads.

## Investigation History review

### API behavior

`GET /api/portal/investigations` is the single history route for both global and
transfer-specific views. It enforces:

- a valid signed operator cookie;
- `limit` from 1 through 50 and non-negative `offset`;
- an optional allowlisted `transferId` limited to TRF-1001 through TRF-1005;
- operator scoping in the SQL predicate;
- newest-first ordering by persisted start time, with PEX as a deterministic
  tie-breaker;
- `Cache-Control: no-store` and a sanitized public projection.

The route returns `items`, `total`, `limit`, and `offset`. It does not return the
operator identifier, idempotency hash, request hash, webhook event ID, webhook
credential, review capability, or document content.

The focused tests verify authentication, operator isolation, filtering,
pagination, empty results, invalid filters, and nullable historical fields.
Schema-v1 and schema-v2 rows are migrated in place and read under schema v3;
the current schema-v3 history path is covered by the same suite. No migration
resets the registry.

### No execution on history open

The global and transfer-specific screens call only the history GET. PEX detail
uses only its persisted detail GET and optional read-only plan GET. Neither
frontend path calls `startInvestigation`, and the tests explicitly assert that
opening, paginating, refreshing, and navigating into history do not call it.

The backend list and detail handlers never call `send_webhook` or `create`.
They may lazily mark an already-expired active row `TIMED_OUT` using its
persisted server deadline. That is expected lifecycle maintenance, not a new
Maestro execution or a financial-state change.

### Outcome fidelity

Automated coverage confirms:

- approved + verified + unresolved exceptions renders workflow success and
  `OPEN EXCEPTIONS`, not brokerage-transfer success;
- rejection renders `REVIEW_REJECTED` / `REJECTED` and no disposition success;
- CLEAN renders `CLEAN` / `NOT_REQUIRED` without a fabricated plan audit;
- timeout renders `TIMED_OUT` with the persisted sanitized error;
- missing historical outcome or verification values render `Not recorded`.

The PEX banner explicitly states, for the split-plus-shortage scenario:
`Workflow completed successfully. The brokerage transfer remains unresolved.`

## Horizontal overflow review

The history table does not clip columns: `.table-wrap` uses `overflow:auto`.
The global table has a 1,180-pixel minimum width and the transfer table a
980-pixel minimum width, so narrow screens intentionally scroll horizontally.

This is functional and not a release blocker. The smallest safe follow-up is to
make each scroll wrapper keyboard-focusable and name it as a region, then add a
short mobile-only “Scroll horizontally for more columns” hint. That preserves
the existing columns and visual design while improving discoverability and
keyboard access. No CSS or component change was made in this audit.

## Security review

### Controls verified

- Private APIs compare `X-API-Key` in constant time and fail closed when the
  key is not configured.
- Portal sessions are HMAC-signed, expire, bind to the configured operator, and
  use `Secure`, `HttpOnly`, `SameSite=Strict` cookies in production.
- Portal starts are allowlisted, body-bounded, rate-limited, active-run-capped,
  and protected by a 16-to-128-character idempotency key.
- Idempotency intent is persisted before the one bounded webhook attempt.
  Uncertain delivery is not automatically retried.
- Webhook URL and authentication value use server-side `SecretStr` settings;
  production requires HTTPS, validates the header name, disallows reserved
  header names, disables redirects, and sanitizes errors.
- Public budgets use the ASGI peer address rather than trusting caller-supplied
  forwarding headers.
- Portal history is operator-scoped and does not expose privileged fields.
- The portal cannot approve or reject; plan capabilities are absent from read
  responses.

### Findings

1. **CSRF header omission is accepted.** `X-CSRF-Token` is optional in the
   route signature, and `_read_session` compares it only when a value is
   supplied. An isolated local request with a signed session and no CSRF header
   returned HTTP 201. Require the header or explicitly fail when it is absent,
   and add a negative regression test. SameSite=Strict is meaningful mitigation
   but does not satisfy the documented double-submit/header check.
2. **Login throttling shares the general public budget.** The access-code
   endpoint receives the public per-client/global request limits, while starts
   also receive stricter operator and capacity limits. This is adequate for the
   bounded fictional demo but is not production identity protection.
3. **Python builds are range-resolved.** The current installed environment has
   no OSV findings and passes `pip check`, but `backend/requirements.txt` uses
   compatible ranges rather than a fully locked production dependency set.
   A future Render build can resolve newer versions. This is a reproducibility
   limitation, not a vulnerability observed in the audited environment.

## Read-only secret and dependency scan

- No private-key, common cloud-token, GitHub token, OpenAI-style token, AWS key,
  or Slack token patterns were found in the audited source/document set.
- Sensitive-assignment pattern hits were limited to test variables and two
  documentation commands that read an already-configured local API key; no
  literal production value was present.
- The production frontend bundle contains none of the sensitive configuration
  identifiers searched, including the portal access key, session secret,
  webhook URL/value, demo capability, or review capability.
- `.gitignore` excludes `.env*` except the example, key material, SQLite files,
  generated data, local Flow bindings, local runtime traces, and dependency
  directories.
- `npm audit --omit=dev` reported zero vulnerabilities.
- A read-only OSV batch query reported zero vulnerability references for all 32
  installed PyPI packages queried.

This was not a scan of the running Render container image, its base operating
system, or historical source-control revisions. No remote SBOM is exposed.

## Documentation review

All 87 local Markdown links resolve. Current API route names match the 51-path
local and production OpenAPI documents. The Render guide correctly requires a
single worker, `/data`, startup migrations, and no `DATABASE_URL`. The judge
guide correctly separates public review, authorized execution, and tenant-owned
bindings/reviewer assignment.

The following statements must not remain unqualified after this audit:

- `README.md`, `PROJECT_PLAN.md`, the judge guide, and the earlier audit call the
  checked-in canonical `.flow` product-valid. Fresh standalone validation
  contradicts that statement; only the source-built candidate validated.
- Earlier audit/gap text said the portal presentation and Investigation History
  deployment was pending. The exact production/local asset hash match now
  closes that deployment gap.
- The CSRF requirement must be described as intended but not fully enforced
  until the missing-header case is rejected.

This report and the updated audit/gap list record the current evidence. The
other guides should be reconciled when the canonical binding and CSRF defects
are approved for repair, so their final instructions describe the repaired
state rather than a temporary exception.

## Remaining release limitations

### High priority before an unqualified PASS

1. Rebuild or narrowly repair the checked-in canonical Flow so the two
   in-solution document-retrieval binding rows are present, then repeat
   standalone validation, semantic comparison, and solution dry-run.
2. Enforce a non-empty matching `X-CSRF-Token` on portal starts and add a
   negative test for missing and incorrect headers.

### Retained limitations

- Native inline-Agent evaluation remains blocked by node-scoped file input;
  only the bounded native CLEAN Flow evaluation has a recorded score.
- A second-tenant import and binding rehearsal is not retained.
- Source/package/deployment provenance is owner-managed outside this workspace.
- Authenticated production history details were owner-observed, not fetched in
  this audit without credentials.
- The history table is horizontally scrollable but its scroll region is not yet
  explicitly keyboard-focusable or labelled.
- No running-container SBOM or operating-system dependency scan is available.

## Final recommendation

**PASS WITH LIMITATIONS.**

The competition demonstration is operational, financially safe, regression
green, deployed with exact portal asset parity, and reproducible from editable
source to a valid 81-node/86-edge candidate. It should not be described as an
unqualified release until the checked-in canonical binding discrepancy and
missing-CSRF-header acceptance are repaired and reverified.

