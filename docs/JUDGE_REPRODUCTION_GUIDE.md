# TransferIQ AI judge reproduction guide

This guide provides three bounded ways to inspect TransferIQ AI. The public path is read-only and requires no credentials. Starting a real portal investigation requires an access code supplied privately by the project owner. Reproducing the UiPath solution in another tenant requires that tenant's own UiPath resources and permissions.

For the checked-in Studio Web archive, use the root-level [TransferIQ `.uis` import, deployment, and run guide](../TRANSFERIQ_UIS_RUN_GUIDE.md). It contains the exact archive checksum, target-tenant rebinding steps, sample Manual Trigger inputs, expected results, and the additional requirements for a judge-owned local portal run. This document remains the broader public/owner/source reproduction guide.

IXP-in-Flow is unavailable in the Community tenant used by this project. TransferIQ therefore uses the supported Autonomous Agent Analyze Files tool with a real PDF file resource and an explicitly labelled `API_ONLY` fallback. Reviewers must keep `enableIXP=false`; no current result should be described as IXP extraction.

## 1. Fastest public review — no credentials

Open the deployed portal:

- Portal: <https://transferiq-api.onrender.com/portal>
- Health: <https://transferiq-api.onrender.com/health>
- OpenAPI: <https://transferiq-api.onrender.com/docs>

The public portal exposes only five allowlisted fictional transfers and precomputed synthetic data. It does not expose private brokerage APIs, credentials, UiPath webhook configuration, approval capabilities, or arbitrary uploads.

Recommended scenarios:

| Transfer | Expected catalog state | What to inspect |
|---|---|---|
| `TRF-1001` | `CLEAN` | Seven positions match directly; no human review is required. |
| `TRF-1002` | `INVESTIGATION_REQUIRED` | SEC-103 has a verified 2-for-1 corporate-action explanation; SEC-104 remains short by 20 shares. |
| `TRF-1003` | `CLEAN` | One position is explained through verified identifier evidence. |
| `TRF-1004` | `CLEAN` quantities | Quantity reconciliation is clean, while missing cost-basis evidence remains a separate review concern. |
| `TRF-1005` | `INVESTIGATION_REQUIRED` | The single quantity exception remains unsupported. |

The public transfer pages are deliberately read-only. A judge can browse the scenario, reconciliation, investigation, review/audit, and document tabs without starting a workflow.

## 2. Owner-authorized live portal demonstration

This path exercises the deployed portal, HTTP Webhook, Maestro Flow, Autonomous Agent, Analyze Files tool, Quick Form, deterministic backend, verification, and audit ledger.

Prerequisites supplied privately by the owner:

- the portal operator access code;
- access to the project's UiPath Action Center if the judge will complete the human task;
- an agreed single test scenario and outcome.

Procedure:

1. Open `TRF-1002` in the production portal and select **Investigation**.
2. Enter the operator access code. The backend returns an HttpOnly session cookie and a CSRF token; the access code is not embedded in the frontend bundle.
3. Select **Investigate with AI** once. Record the returned `PEX-...` execution request ID.
4. Open **View Maestro progress**. Confirm that the persisted timeline moves through `PENDING`, `TRIGGERED`, `INVESTIGATING`, and `AWAITING_HUMAN_REVIEW` as applicable.
5. Complete the real Quick Form in UiPath Action Center. Approval and rejection are intentionally unavailable in the portal.
6. Return to or refresh the same `PEX-...` tracking URL. Refresh must not create another execution.
7. For approval, expect workflow outcome `REVIEWED_WITH_OPEN_EXCEPTIONS`, verification `VERIFIED_DEMO_STATE`, SEC-104 `UNRESOLVED / -20`, `positionsUnchanged=true`, and `transferCompleted=false`.
8. For rejection, expect `REVIEW_REJECTED`, unchanged positions, and no transfer completion.
9. Open the audit report and confirm the persisted review and disposition events.

Guardrails:

- Use one bounded submission; do not repeatedly start the same scenario.
- Only one active investigation is allowed per operator.
- The browser polls only while the record is active and stops after its bounded client window. Manual refresh reads the same durable record.
- The backend workflow timeout is independent of the browser polling window.
- A webhook HTTP 200 means accepted/triggered, not completed.
- Never share the webhook URL, authentication header value, session secret, operator access code, capability token, or signed document URL.

Existing sanitized real-run evidence is cataloged in [LIVE_EXECUTION_EVIDENCE.md](LIVE_EXECUTION_EVIDENCE.md). No new live execution is required to review those records.

## 3. Local backend and frontend verification

Prerequisites:

- Python compatible with the checked-in environment;
- Node.js and npm;
- the repository source;
- no production credentials.

From the repository root:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q --tb=short
python -m compileall -q backend scripts
python -m pip check

Set-Location frontend
npm test -- --run
npm run build
npm audit --omit=dev
```

The tests use isolated synthetic state and identified test doubles where external UiPath behavior must be simulated. They do not constitute a new real UiPath execution or human approval.

To run the application locally, copy `.env.example` to a local ignored `.env`, set only the required local values, and follow [README.md](../README.md). Do not commit `.env` or any generated database, PDF, binding, or user-profile material.

## 4. Rebuild and validate the checked-in UiPath Flow

The Flow source has a pinned local toolchain. First prepare target-tenant values in the ignored `.flow-sdk/bindings.json`: either copy `bindings.example.json` and replace its placeholders, or run the registry preparation command in section 5. Never commit the resulting file.

```powershell
Set-Location maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation\.flow-sdk
npm ci
npm run check

$candidateDir = Join-Path $env:TEMP 'transferiq-flow-candidate'
New-Item -ItemType Directory -Path $candidateDir -Force | Out-Null
$candidate = Join-Path $candidateDir 'TransferIQ_Reconciliation.flow'

.\node_modules\.bin\flow-sdk.cmd flow compile `
  .\TransferIQ_Reconciliation.flow.ts `
  -o $candidate `
  --bindings .\bindings.json

node .\finalize-agent-contract.mjs $candidate
.\node_modules\.bin\uip.cmd maestro flow validate $candidate --output json
node .\compare-flow-structure.mjs ..\TransferIQ_Reconciliation.flow $candidate
```

Expected source-build results:

- source check: 0 errors and 0 warnings;
- compile: 81 nodes and 86 edges;
- product validation: `Success / Valid`;
- semantic comparison: `valid: true`, with no missing/extra node IDs or edge tuples and equivalent Quick Form/agent input contracts.

The finalization step is required because SDK `returns` cannot express the complete required agent output contract, and source/runtime prompt reference forms differ. It supplies schema only; it does not create model output or runtime defaults. Compile outside the project so the checked-in canonical Flow is never replaced accidentally.

The lockfile pins UiPath CLI 1.205.0. CLI 1.206.0 currently misvalidates the dynamic Approve/Reject Quick Form ports in both the unchanged canonical Flow and an equivalent rebuilt Flow; do not rewire working outcome ports merely to satisfy that regression. See [MAESTRO_SOURCE_REPRODUCIBILITY.md](MAESTRO_SOURCE_REPRODUCIBILITY.md).

For the remaining checked-in UiPath artifacts, authenticate the UiPath CLI with your own account and run from the repository root:

```powershell
uip login

uip maestro flow validate `
  maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation\TransferIQ_Reconciliation.flow `
  --output json

uip api-workflow validate `
  maestro\TransferIQ_Reconciliation\TransferIQ_Document_Retrieval\Workflow.json `
  --output json

uip solution pack maestro\TransferIQ_Reconciliation --dry-run --output json
```

Expected results for the audited checkout:

- canonical Maestro Flow: `Valid`, 81 nodes and 86 edges. Its only repair was
  the two process binding rows required by `RetrieveCorporateActionDocument`;
- document-retrieval API workflow: `Valid` and buildable;
- solution dry-run: `Success / Valid`, with the known pre-existing `ImplicitConnection` catalog advisory.

The source-built candidate and canonical intentionally need not be byte-identical.
The semantic comparison must report no missing/extra node IDs or edge tuples,
equivalent Quick Form outcomes, and equivalent Agent inputs. The canonical's
pre-repair and repaired SHA-256 values are recorded in
[`maestro/verification-backups/SHA256SUMS.md`](../maestro/verification-backups/SHA256SUMS.md).

## 5. Import into a judge-owned UiPath tenant

This is not a zero-configuration path. It uses the judge's own tenant, licenses, identity, connection, and reviewer assignment. Do not reuse the project owner's identifiers or secrets.

The preferred import artifact is [`TransferIQ_Reconciliation.uis`](../TransferIQ_Reconciliation.uis). Follow the [root `.uis` run guide](../TRANSFERIQ_UIS_RUN_GUIDE.md) for the complete procedure. The source-directory command below remains useful for developers rebuilding from editable source.

1. Confirm entitlement to Maestro, Agents, Integration Service, Action Center, and the model/tool capabilities used by Analyze Files.
2. Authenticate the UiPath CLI to the intended organization, tenant, and folder.
3. Upload either the checked-in `.uis` or the source solution project:

   ```powershell
   uip solution upload .\TransferIQ_Reconciliation.uis --output json
   # Source-developer alternative:
   uip solution upload .\maestro\TransferIQ_Reconciliation --output json
   ```

   In a separate judge tenant, the expected `.uis` action is `Imported`. If the response says `Overwritten`, confirm that replacing the existing Studio Web solution is intentional before continuing.

4. In the solution configuration, resolve every imported resource with resources owned by that tenant.
5. Open Transfer Operations Review in the Flow designer. In Assignment criteria,
   select one assignable user from the target folder/tenant and keep Action Center
   delivery enabled. Save the form, then confirm the generated node still has the
   same Approve and Reject outcomes. The owner-tenant reviewer/default email is
   not portable and must not be copied as a tenant binding.
6. If the portal-triggered path is required, create an authenticated HTTP Webhook connection, then prepare the binding using the real connection ID:

   ```powershell
   uip maestro registry prepare uipath-http-webhook `
     --action http-webhook `
     --connection-id <CONNECTION_ID>
   ```

7. Configure the deployed backend with the new webhook URL and matching authentication header through secret environment settings. Never put them in Flow source or frontend variables.
8. Validate, publish, deploy, and activate in the chosen folder. The owner
   deployment is version 1.1.2; retained end-to-end runtime evidence is from 1.1.1. A judge-owned import may receive a different
   tenant-local package version and must be reported as a separate deployment.
9. For an initial proof, use the Manual Trigger shown by the imported Flow designer and supply its required values. Keep `enableIXP=false`; the document path uses the Autonomous Agent's Analyze Files tool, not IXP-in-Flow.
10. Run one test, inspect the actual agent tool invocation, complete the Action Center task, and verify the final plan and audit endpoints.

The automated portal route retrieves the allowlisted fictional PDF through `TransferIQ_Document_Retrieval` and passes a real file resource to Analyze Files. A URL string alone is not a substitute for that file input.

## 6. Expected acceptance evidence

A successful `TRF-1002` approval demonstration should show all of the following:

- the document retrieval workflow returned the fictional corporate-action PDF;
- the Autonomous Agent invoked Analyze Files against a real file attachment;
- extracted SEC-103 fields were labeled `AGENT_ANALYZE_FILES` and initially treated as document evidence, not independent verification;
- the deterministic validator matched the extraction to corporate action `CA-2026-081` before promoting it to verified evidence;
- SEC-104 remained expected 120 versus staged 100, difference `-20`;
- a real Quick Form captured the authorized human decision;
- plan verification returned `VERIFIED_DEMO_STATE`;
- original brokerage positions remained unchanged and no correction was applied;
- the audit endpoint returned the expected append-only events.

For `TRF-1001`, the Flow should reach `CLEAN` without invoking document retrieval, the agent, or the Quick Form.

## 7. Evidence and limitations

- Final audit: [FINAL_PROJECT_AUDIT.md](FINAL_PROJECT_AUDIT.md)
- Feature matrix: [FEATURE_COMPLETENESS_MATRIX.md](FEATURE_COMPLETENESS_MATRIX.md)
- Sanitized live evidence: [LIVE_EXECUTION_EVIDENCE.md](LIVE_EXECUTION_EVIDENCE.md)
- Prioritized gaps: [SUBMISSION_GAP_LIST.md](SUBMISSION_GAP_LIST.md)
- Portal integration: [STEP10B_PORTAL_MAESTRO_INTEGRATION.md](STEP10B_PORTAL_MAESTRO_INTEGRATION.md)
- Document analysis: [STEP11_AGENT_DOCUMENT_ANALYSIS.md](STEP11_AGENT_DOCUMENT_ANALYSIS.md)

The audit did not launch a new business execution, change financial logic, deploy a new solution, or perform a new human approval. Historical live evidence is clearly separated from fresh read-only verification.
