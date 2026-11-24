# Import, deploy, and run the TransferIQ UiPath solution

This is the reviewer-facing guide for the checked-in UiPath Studio Web export:

[`TransferIQ_Reconciliation.uis`](TransferIQ_Reconciliation.uis)

The exact filename is `TransferIQ_Reconciliation.uis` (singular *Reconciliation*). The archive contains both required projects:

- `TransferIQ_Reconciliation` — the 81-node/86-edge Maestro Flow;
- `TransferIQ_Document_Retrieval` — the API Workflow that returns the run-scoped fictional PDF as a file resource.

The `.uis` is editable solution source, not an already deployed package. Importing it does not deploy or run a workflow. A reviewer must use a UiPath tenant with Maestro, Agents, Integration Service, and Action Center access, then supply that tenant's own connection and reviewer assignment.

## Package integrity and validated contents

| Item | Value |
|---|---|
| File | `TransferIQ_Reconciliation.uis` |
| Size | 579,055 bytes |
| SHA-256 | `5589B77E038CB31F4D2385DE9BD075807D311456258B9B539B1334B46C349F19` |
| Projects | `TransferIQ_Reconciliation`, `TransferIQ_Document_Retrieval` |
| Flow graph | 81 nodes, 86 edges, 2 triggers |
| Toolchain | UiPath CLI 1.205.0 |

The checked-in archive was inspected and dry-run packed. Its Flow and API Workflow independently validated as `Valid`. The dry run reported only the existing `ImplicitConnection` resource-catalog advisory. No workflow was executed as part of that inspection.

Verify the file after cloning:

```powershell
Get-FileHash .\TransferIQ_Reconciliation.uis -Algorithm SHA256
```

## Choose a review path

| Path | Best for | Backend used | Portal start |
|---|---|---|---|
| A. Manual Orchestrator run | Fastest real UiPath proof | Existing hosted fictional demo API | No |
| B. Judge-owned portal run | Full Portal → Maestro lifecycle | Judge-owned public HTTPS backend | Yes |
| C. Read-only/local application review | UI and automated tests without UiPath credits | Localhost | No real Flow start |

**Path A is recommended for judging.** It proves the real Flow, document retrieval, Analyze Files, and Quick Form without requiring the judge to operate a public backend. Path B is available when full ownership of the portal webhook and PEX tracking is required.

## Prerequisites

1. A separate UiPath organization/tenant with:
   - Maestro/Flows;
   - Agents and the built-in Analyze Files capability;
   - Integration Service HTTP Webhook connector;
   - Action Center;
   - permission to publish and deploy a Solution.
2. One assignable reviewer user in the deployment folder.
3. Node.js/npm to restore the pinned CLI, or an independently installed **UiPath CLI 1.205.0**.
4. The GitHub checkout containing this `.uis` file.

Do not use CLI 1.206.0 for this artifact. That version has a known validation regression for the Flow's dynamic Quick Form Approve/Reject ports.

## 1. Restore and verify the pinned CLI

From the repository root:

```powershell
Set-Location .\maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation\.flow-sdk
npm ci
.\node_modules\.bin\uip.cmd --version
Set-Location ..\..\..\..

$uip = (Resolve-Path .\maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation\.flow-sdk\node_modules\.bin\uip.cmd).Path
& $uip solution pack .\TransferIQ_Reconciliation.uis --dry-run --output json
```

Expected dry-run result: `Success / Valid`. The `ImplicitConnection` catalog message is a known advisory for the existing managed backend HTTP activity; it is not a missing webhook secret.

## 2. Import into a separate Studio Web solution

Sign in to the judge's tenant:

```powershell
& $uip login
& $uip solution upload .\TransferIQ_Reconciliation.uis --output json
```

Record `Data.Action`, `Data.SolutionId`, and `Data.DesignerUrl` from the response. In a different tenant, the expected action is `Imported`.

> **Owner-tenant warning:** the archive carries its source Studio Web `SolutionId`. If a solution with that ID already exists in the signed-in tenant, `solution upload` overwrites it in place after creating a snapshot. Judges should import into their own tenant. Do not upload this archive into the project owner's production tenant merely to test it.

The same import can be initiated from Studio Web's Solutions import/upload control by selecting `TransferIQ_Reconciliation.uis`. The CLI route is preferred because it reports whether the action was `Imported` or `Overwritten`.

## 3. Replace non-portable tenant settings

Open the returned `DesignerUrl` and configure the imported solution before publishing.

### 3.1 Quick Form reviewer

Open `TransferIQ_Reconciliation` → `Transfer Operations Review`:

1. Keep assignment type **Single user**.
2. Select an eligible user from the judge's tenant/folder.
3. Keep Action Center delivery enabled.
4. Preserve the two outcomes exactly: **Approve** and **Reject**.
5. Save the Flow.

The owner-tenant user selection is not portable. In the Manual Trigger input, replace the saved default `reviewerReference` with a judge-controlled label such as the reviewer's email. This value is an audit reference, not authorization by itself.

### 3.2 HTTP Webhook connection

This resource is required for Path B and should still be rebound for a clean portable deployment:

1. In Integration Service, create an **HTTP Webhook** connection in the target folder.
2. Choose header authentication.
3. Use a new random header name/value owned by the judge. Do not reuse or request the project owner's value.
4. Bind the `PortalWebhook` trigger to that connection.
5. Complete connection authentication/setup if deployment reports `NeedsSetupToActivate`.

The authentication value belongs only in Integration Service and the judge's backend environment. It must not be pasted into the Flow, GitHub, or a browser variable.

### 3.3 Backend URL

For **Path A**, retain the imported value:

```text
https://transferiq-api.onrender.com
```

This is the public fictional run-isolated backend. It does not require the private `X-API-Key` for `/api/demo/runs` operations.

For **Path B**, replace all three backend-base locations with one judge-owned public HTTPS origin:

1. the Flow global variable `backendBaseUrl`;
2. the document-list URL in `TransferIQ_Document_Retrieval`;
3. the document-content URL in `TransferIQ_Document_Retrieval`.

UiPath Cloud cannot call `127.0.0.1` or `localhost`. If the backend runs on the judge's computer, expose port 8000 with a temporary HTTPS tunnel and use that public origin. Do not mix a local portal registry with the owner Render backend: their `PEX-...` records are different databases and correlation will fail.

### 3.4 Preserve these settings

- `enableIXP=false` — the implemented document path is Autonomous Agent **Analyze Files**, not IXP-in-Flow.
- Manual Trigger entry point: `StartTransferInvestigation`.
- Portal entry point: `PortalWebhook`.
- Both solution projects must be published and deployed together.
- Do not remove or replace the API Workflow binding used by `RetrieveCorporateActionDocument`.

## 4. Validate, publish, and deploy

The simplest approach is to use the imported solution's **Publish** and **Deploy** actions in Studio Web after saving the target-tenant settings. Choose a new judge-owned package name/version and a new folder. Do not upgrade the project owner's deployment.

For a CLI deployment, first download the saved target-tenant solution so the package contains the judge's changes:

```powershell
New-Item -ItemType Directory -Path .\judge-export -Force | Out-Null
& $uip solution download <JUDGE_SOLUTION_ID> `
  --destination .\judge-export `
  --name TransferIQ_Reconciliation.judge `
  --output json

New-Item -ItemType Directory -Path .\dist -Force | Out-Null
& $uip solution pack .\judge-export\TransferIQ_Reconciliation.judge.uis .\dist `
  --name TransferIQ-AI-Judge `
  --version 1.0.0 `
  --output json

& $uip solution publish .\dist\TransferIQ-AI-Judge_1.0.0.zip `
  --wait `
  --output json

& $uip solution deploy run `
  --name "TransferIQ-AI Judge" `
  --package-name TransferIQ-AI-Judge `
  --package-version 1.0.0 `
  --folder-name TransferIQ-AI-Judge `
  --output json
```

If the pack command reports a different output filename, use the exact `Data.Output` path it returns for `solution publish`.

An activation result of `NeedsSetupToActivate` is not a failed deploy. Open the named deployment in Orchestrator, authenticate/configure the pending connection, and activate the same deployment. Do not deploy a second copy to work around setup activation.

After activation, confirm that Orchestrator shows both processes:

- `TransferIQ_Reconciliation`;
- `TransferIQ_Document_Retrieval`.

## 5. Recommended manual acceptance run

In Orchestrator, select **Processes** → `TransferIQ_Reconciliation` → **Start job** and choose entry point `StartTransferInvestigation`.

### CLEAN control

Use:

```json
{
  "transferId": "TRF-1001",
  "reviewerReference": "judge@example.test",
  "enableIXP": false,
  "corporateActionPdf": null
}
```

Expected behavior:

- outcome `CLEAN`;
- seven matched positions;
- no document retrieval, Agent call, or Quick Form task.

### Analyze Files and human-review scenario

Use:

```json
{
  "transferId": "TRF-1002",
  "reviewerReference": "judge@example.test",
  "enableIXP": false,
  "corporateActionPdf": null
}
```

Leave the file input empty. The Flow should call `TransferIQ_Document_Retrieval`, receive the actual fictional PDF as a file resource, and pass that file to the Agent's Analyze Files tool.

Expected document evidence:

| Field | Expected fictional value |
|---|---|
| `securityId` | `SEC-103` |
| `actionType` | `STOCK_SPLIT` |
| `splitNumerator` | `2` |
| `splitDenominator` | `1` |
| `effectiveDate` | `2026-08-10` |
| `noticeDate` | `2026-08-15` |
| `evidenceReference` | `CA-2026-081` |

The extraction is document evidence only. The Flow must compare it with the independent corporate-action API before treating SEC-103 as explained.

When the Action Center task appears, add a comment and choose one outcome:

- **Approve:** expect `REVIEWED_WITH_OPEN_EXCEPTIONS` and `VERIFIED_DEMO_STATE`. SEC-103 is acknowledged, while SEC-104 remains expected 120 versus received 100 (`-20`). `positionsUnchanged=true`, `transferCompleted=false`, and `correctionsApplied=0`.
- **Reject:** expect `REVIEW_REJECTED`, unchanged positions, and `transferCompleted=false`.

Workflow completion does **not** mean the fictional brokerage transfer completed. TRF-1002 deliberately retains its unresolved 20-share shortage.

Run only one TRF-1002 outcome unless a second outcome is necessary for judging. Agent calls and Action Center tasks consume tenant resources.

## 6. Other sample transfer IDs

| Transfer | Expected route | Important result |
|---|---|---|
| `TRF-1001` | CLEAN | No Agent or human task. |
| `TRF-1002` | Investigation | Verified 2-for-1 split explains SEC-103; SEC-104 remains `-20`. |
| `TRF-1003` | CLEAN | Identifier mapping explains the apparent mismatch. |
| `TRF-1004` | Quantity CLEAN | Missing cost-basis evidence remains a separate review concern; unknown basis is never treated as zero. |
| `TRF-1005` | Investigation | Unsupported quantity correction remains unresolved. |

Only these five fictional IDs are accepted by the demo contract.

## 7. Full judge-owned portal path

Use this only when the reviewer wants to initiate the Flow from a locally controlled TransferIQ portal rather than Orchestrator.

### 7.1 Start the backend and portal locally

Copy `.env.example` to the ignored `.env` and set these local values:

```text
APP_ENV=development
DATA_DIR=./data
PUBLIC_DEMO_ENABLED=1
DEMO_EXECUTION_ENABLED=1
PORTAL_INVESTIGATION_ENABLED=1
PORTAL_OPERATOR_ID=judge-operator
PORTAL_OPERATOR_ACCESS_KEY=<at least 16 random characters>
SESSION_SECRET=<at least 32 random characters>
PORTAL_SESSION_TTL_MINUTES=10
PORTAL_USER_MAX_ACTIVE=1
PORTAL_GLOBAL_MAX_ACTIVE=3
PORTAL_STARTS_PER_MINUTE=2
PORTAL_WORKFLOW_TIMEOUT_MINUTES=10
UIPATH_WEBHOOK_URL=<judge tenant's deployed webhook URL>
UIPATH_WEBHOOK_AUTH_HEADER_NAME=X-TransferIQ-Webhook-Key
UIPATH_WEBHOOK_AUTH_HEADER_VALUE=<the judge connection's matching random value>
UIPATH_WEBHOOK_TIMEOUT_SECONDS=15
```

Then run:

```powershell
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
& .\.venv\Scripts\python.exe -m backend.database.init_db
& .\.venv\Scripts\python.exe -m backend.database.seed
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
npm ci --prefix frontend
npm run dev --prefix frontend
```

Open <http://127.0.0.1:5173/portal/>. Vite proxies `/api` calls to port 8000.

### 7.2 Make the backend reachable from UiPath Cloud

Expose local port 8000 through a reviewer-controlled temporary HTTPS tunnel. Configure the imported Flow and both API Workflow URLs to that HTTPS origin as described in section 3.3, then publish/deploy that judge-owned solution.

The local backend sends one authenticated POST to the deployed UiPath webhook. The Flow then calls the same public HTTPS origin for the PEX-correlated demo run, document, plan, verification, and audit APIs.

### 7.3 Start from the portal

1. Open `TRF-1002` → **Investigation**.
2. Enter the local `PORTAL_OPERATOR_ACCESS_KEY`.
3. Click **Investigate with AI** once.
4. Record the returned `PEX-...` ID.
5. Follow the six-stage timeline: started, Maestro triggered, AI investigation, awaiting review, decision recorded, verified result.
6. Complete the real Quick Form in Action Center.
7. Refresh the same PEX page. Refreshing reads the persisted record and must not start another Flow.

The webhook's HTTP 200 response means only that UiPath accepted the event. The portal marks completion only after the correlated plan, verification, and audit data are persisted.

### API-only portal start example

The browser already performs this sequence. For diagnostics, an authorized reviewer can reproduce it with PowerShell:

```powershell
$portal = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$login = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/portal/session `
  -WebSession $portal `
  -ContentType 'application/json' `
  -Body (@{ accessCode = '<local access code>' } | ConvertTo-Json)

$headers = @{
  'X-CSRF-Token' = $login.csrfToken
  'Idempotency-Key' = 'judge-trf1002-0001'
}

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/portal/investigations `
  -WebSession $portal `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body (@{ transferId = 'TRF-1002' } | ConvertTo-Json)
```

Reuse the same idempotency key only to read the same start result. Do not generate repeated real starts while diagnosing a failure.

## 8. Read-only local review without a UiPath deployment

The public catalog and local UI can be reviewed without starting Maestro. Leave `PORTAL_INVESTIGATION_ENABLED=0`, run the backend/frontend commands above, and browse the five synthetic transfers. Automated regression tests use isolated data and explicit test doubles; they are not proof of a live Agent or Quick Form run.

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --tb=short
npm test --prefix frontend -- --run
npm run build --prefix frontend
```

## 9. Troubleshooting

| Symptom | Check |
|---|---|
| Import says `Overwritten` | You signed into a tenant containing the bundled solution ID. Stop if this is not an intentional owner-tenant update; use a separate tenant. |
| Deployment says `NeedsSetupToActivate` | Authenticate/configure the imported HTTP Webhook connection, then activate the same deployment. |
| Quick Form returns AppTasks HTTP 400 | Re-open the form, select a real assignable single user in the deployment folder, save, republish, and deploy. |
| Portal says an investigation is already active | Open the existing PEX record or wait for its configured server timeout. Do not create duplicate starts. |
| Portal webhook is accepted but PEX never advances | Confirm the Flow and local portal point to the same public backend origin. UiPath Cloud cannot call localhost. |
| Document retrieval fails | Confirm `TransferIQ_Document_Retrieval` is deployed with the Flow and both of its URLs use the same backend origin. |
| Agent reports no file | Confirm the API Workflow returns a file resource, not only a URL string, and that Analyze Files is available in the tenant. |
| IXP option is visible on Manual Trigger | Keep it false. It is a legacy compatibility input; this solution uses Analyze Files. |
| CLI 1.206.0 reports Quick Form port errors | Restore the checked-in lockfile and use CLI 1.205.0. Do not rewire the working outcomes. |

## Security and evidence rules

- Never commit `.env`, webhook URLs, authentication values, operator codes, session secrets, reviewer capabilities, or target-tenant bindings.
- Do not publish the owner-specific user profile/debug material contained in an extracted `.uis` as deployment evidence.
- The solution contains only fictional brokerage data and documents.
- AI extraction is untrusted until deterministic API validation succeeds.
- No real custody position is changed. The demo dispositions and audit ledger are scoped to the isolated synthetic run.
- Record the judge-owned package version, Flow instance ID, PEX ID (for portal starts), Action Center task ID, final outcome, verification status, and incident count. Do not relabel the project's retained 1.1.1 evidence as a new run.

## Related documentation

- [README](README.md)
- [Judge reproduction guide](docs/JUDGE_REPRODUCTION_GUIDE.md)
- [Flow source reproducibility](docs/MAESTRO_SOURCE_REPRODUCIBILITY.md)
- [Portal lifecycle](docs/STEP10C_PORTAL_STATUS.md)
- [Agent document analysis](docs/STEP11_AGENT_DOCUMENT_ANALYSIS.md)
- [Render deployment](docs/RENDER_DEPLOYMENT.md)

