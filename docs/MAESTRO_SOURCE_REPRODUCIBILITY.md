# Maestro Flow source reproducibility

Status: **source remediated on 2026-11-19; checked-in canonical artifact repaired and independently validated on 2026-11-22; repaired solution published and activated as 1.1.2 on 2026-11-24**. This procedure rebuilds a product-valid candidate and validates the checked-in canonical Flow. The 1.1.2 release installation did not launch a Maestro execution; retained functional evidence remains from 1.1.1.

## What was repaired

The audited source check originally reported three errors and three warnings:

| Diagnostic | Root cause | Repair |
|---|---|---|
| `HITL_OUTCOME_PORT_MISPLACED` (Approve) | The Quick Form was authored as a generic raw node, so the checker did not recognize its dynamic outcome port. | Replaced the raw source declaration with typed `hitl(...)` plus `stepSwitch(...)`; preserved form node ID `quickForm1` and outcome ID `submit`. |
| `HITL_OUTCOME_PORT_MISPLACED` (Reject) | Same raw-node issue for `outcome-outcome-1794281395070`. | Preserved that exact outcome ID and routed it through the typed Reject arm. |
| `REF_INTO_PORT_LIST` | The Reject branch jumped into another port-list path at `RecordReviewDecision`. | Both typed outcome arms now finish their existing disposition node and converge on the existing decision step in the parent chain. |
| `INLINE_AGENT_UNREFERENCED_INPUT` | Source prompts used runtime expressions instead of source-level `{{input.*}}` references, so SDK input derivation could prune them. | Source uses `{{input.SerializeInvestigationContext__output}}` and `{{input.agentDocument}}`; finalization preserves the deployed direct-expression runtime prompt. |
| `RAW_NODE_TYPED_FAMILY` | `quickForm1` used `rawNode(...)` even though the SDK has a typed HITL family. | The source now uses `hitl({ variant: "quick-form" })`. |
| `NO_RETURN` | Raw port-list topology prevented the checker from proving every review path terminated. | Typed Approve and Reject arms converge on the unchanged review, execute, verify, audit and return chain. |

The repair also restores the actual agent file binding (`agentDocument: v("agentDocument")`) used by automated document retrieval. It does not bind Analyze Files to the Manual Trigger field alone.

## Canonical artifact binding repair

The pre-repair canonical artifact contained 81 nodes and 86 edges, but UiPath
CLI 1.205.0 reported one error and two warnings at
`RetrieveCorporateActionDocument`: `<bindings.name>` and
`<bindings.folderPath>` were unresolved, and the API Workflow definition's
existing resource key was absent from `workflow.bindings[]`.

The supported `uip maestro flow bindings create` command added exactly two
process rows. No node, edge, definition, expression, layout, Agent contract or
Quick Form field/outcome changed:

| Name/property | Resource | Resource key | Default | Subtype |
|---|---|---|---|---|
| `name` | `process` | `b41e40a5-172f-465d-8aee-01d75ea8e906` | `TransferIQ_Document_Retrieval` | `Api` |
| `folderPath` | `process` | `b41e40a5-172f-465d-8aee-01d75ea8e906` | `solution_folder` | `Api` |

The resource key was not invented: it is the existing key embedded in the
canonical node type and definition and is the exact key named by the validator.
The source-built candidate serializes the same logical in-solution resource as
`solution_folder.TransferIQ_Document_Retrieval`; this compiler-level resource
key representation differs, while the API Workflow name, folder, node type and
inputs are semantically equivalent.

The pre-repair backup is outside the solution project at
`maestro/verification-backups/TransferIQ_Reconciliation.flow.pre-binding-repair-20261122.bak`.
Checksums are recorded in
[`maestro/verification-backups/SHA256SUMS.md`](../maestro/verification-backups/SHA256SUMS.md).

## Pinned development tools

The checked-in `.flow-sdk/package.json` and lockfile pin:

- `@uipath/maestro-builder-sdk` 6.66.5
- `@uipath/cli` 1.205.0

Use the pinned CLI for this artifact. UiPath CLI 1.206.0 currently rejects the dynamic Quick Form outcome handles in both the unchanged working canonical artifact and the rebuilt candidate, while 1.205.0 validates the candidate as `Valid`. This is a CLI manifest-registry compatibility limitation, not a reason to rewire the deployed Approve/Reject behavior.

## Tenant-local bindings

Real binding values remain excluded by `.gitignore`. Copy `.flow-sdk/bindings.example.json` to `.flow-sdk/bindings.json` and replace every angle-bracket placeholder with resources from the target tenant. The required labels are:

- `portalHttpWebhook`: the target tenant's authenticated HTTP Webhook connection ID;
- `shared`: the Orchestrator folder key used by that connection.

When authenticated to the target tenant, the supported preparation command is:

```powershell
Set-Location maestro\TransferIQ_Reconciliation\TransferIQ_Reconciliation
uip maestro registry prepare uipath-http-webhook `
  --action http-webhook `
  --connection-id <CONNECTION_ID>
```

Review the generated `.flow-sdk/bindings.json`; do not commit it. The in-solution `TransferIQ_Document_Retrieval` reference and `solution_folder` folder path are authored in source and remain unchanged.

## Clean source-to-candidate build

Run from a clean checkout after preparing the tenant-local binding file:

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

node .\compare-flow-structure.mjs `
  ..\TransferIQ_Reconciliation.flow `
  $candidate

.\node_modules\.bin\uip.cmd maestro flow validate `
  ..\TransferIQ_Reconciliation.flow `
  --output json
```

Compile outside the Flow project so a candidate cannot replace the working canonical artifact. `finalize-agent-contract.mjs` is required: the SDK's primitive `returns` syntax cannot express the full required output schema, and the installed agent node requires resolved runtime expressions while source checking requires `{{input.*}}` references.

## Verified result

The clean-directory verification performed for this remediation produced:

- source check: **0 errors, 0 warnings**;
- compile: **81 nodes, 86 edges**;
- product validation with pinned UiPath CLI 1.205.0: **Success / Valid**;
- checked-in canonical validation with the same CLI: **Success / Valid**;
- node ID comparison: no missing or extra IDs;
- edge comparison: no missing or extra source/target/port tuples;
- critical node types: unchanged;
- Quick Form fields, outcomes, recipient configuration and version: semantically equivalent;
- agent input variables: semantically equivalent, including the file-capable `agentDocument` binding.
- document-retrieval inputs remain `$vars.ValidateDemoRun.output.runId` and `$vars.ValidateInput.output.transferId` in both artifacts;
- parsed pre/post canonical difference: exactly two appended `workflow.bindings[]` rows.

Byte-for-byte equality is not expected because compilation regenerates schema IDs, UI metadata and serialization order. The comparison script deliberately checks business-critical graph semantics instead.

## Regression results

- Focused Maestro/portal/agent/document contract checks after canonical repair: **171 passed**, one existing Starlette/httpx deprecation warning, 74.08 seconds.
- Complete post-repair backend regression: **485 passed**, the same known warning, 349.05 seconds.
- First full backend rerun: **476 passed, 2 failed**. Both failures detected that a diagnostic compile had emitted the primitive SDK agent schema into the working sidecar. The required schema was restored and build output was isolated outside the project; this failed run is not counted as success.
- Final full backend rerun: **478 passed**, one existing Starlette/httpx deprecation warning, **172.64 seconds**.
- Frontend unit suite: **18 passed**.
- Frontend production build: **successful**.

No live UiPath, Action Center or Render test was executed for this artifact-only remediation.

## Remaining limitations

- A target tenant must supply its own webhook connection, folder, reviewer assignment eligibility, model entitlement and solution resources.
- A second-tenant import rehearsal was not performed in this remediation.
- UiPath CLI 1.206.0 has the dynamic Quick Form validation regression described above; keep 1.205.0 pinned until UiPath resolves it or a newer verified version is adopted.
- No Render or UiPath deployment and no production Maestro execution was performed.
