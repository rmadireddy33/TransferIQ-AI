# Step 11 — Autonomous Agent document evidence analysis

Status: **Phase A and Phase B are live-verified. Active solution 1.1.1 completed real no-upload portal-triggered TRF-1002 approval and rejection runs, plus a TRF-1001 CLEAN control. The rejection run used automated PDF retrieval, a genuine Analyze Files tool call, deterministic document/API validation, a real Quick Form rejection, independent verification, and append-only audit. SEC-104 remained unresolved at -20, positions were unchanged, and IXP was not invoked.**

The existing Manual Trigger, `PortalWebhook`, Autonomous Agent, Quick Form, review ledger, audit path, deterministic reconciliation, and financial immutability rules are preserved. IXP remains disabled by default and was not invoked.

## Safety and evidence boundary

The agent supports two honest evidence routes:

- `AGENT_ANALYZE_FILES` when a real PDF job attachment is available.
- `API_ONLY` when file analysis is unavailable or no suitable document can be retrieved.

Analyze Files output is untrusted document evidence. `ValidateInvestigation` compares its corporate-action fields with the independently fetched corporate-action API before assigning `VERIFIED`. Missing or contradictory values produce `REVIEW_REQUIRED`. An extracted document can never authorize a financial correction. SEC-104 remains governed by deterministic reconciliation and stays unresolved unless independently verified evidence explains it.

The structured document result contains `documentId`, `documentType`, `extractedFields`, `sourceEvidenceReference`, `extractionMethod`, `validationStatus`, `discrepancies`, and `missingFields`. `extractionMethod=AGENT_ANALYZE_FILES` means the built-in agent tool analyzed a file. It does not mean IXP ran.

## Phase A — real file analysis verified

The user supplied Studio Web debug instance `a99ae4d3-242d-43fc-bf92-eead087dbbc3`. Read-only inspection found:

| Item | Actual result |
|---|---|
| Flow instance | `a99ae4d3-242d-43fc-bf92-eead087dbbc3` |
| Instance state | Completed; no incidents |
| Start / end | 2026-11-13 02:36:31.893 UTC / 02:39:20.793 UTC |
| Agent job | `1d828568-6df6-4222-afc4-5be0cd365401` — Successful |
| Analyze Files | Real `Analyze_Files` tool state updates and a successful PDF attachment download were present in the agent job logs |
| Quick Form | Task `100313544` completed with Approve |
| Demo run | `DEMO-95cfd248680a41f39b633ac7dddd2c93` |
| Reconciliation | `REC-96fd50e7-f950-4eb5-a387-17bd76e386b3` |
| Resolution plan | `PLAN-8202710c-cef1-4d1b-8409-512d37736467` — EXECUTED |
| Final result | `REVIEWED_WITH_OPEN_EXCEPTIONS` / `VERIFIED_DEMO_STATE` |

The genuine extracted document evidence was:

```text
documentType: CORPORATE_ACTION_NOTICE
securityId: SEC-103
actionType: STOCK_SPLIT
splitNumerator: 2
splitDenominator: 1
effectiveDate: 2026-08-10
noticeDate: 2026-08-15
evidenceReference: CA-2026-081
extractionMethod: AGENT_ANALYZE_FILES
```

The agent initially labelled its own extraction `NOT_VALIDATED`. The deterministic validator independently matched it to corporate action `CA-2026-081` and promoted the evidence to `VERIFIED`. SEC-103 was explained. SEC-104 remained `UNRESOLVED`, expected/source quantity 120 versus receiving quantity 100, difference `-20`.

The final verification reported `positionsUnchanged=true`, `transferCompleted=false`, and `correctionsApplied=0`. Audit GET returned HTTP 200 and contained `PLAN_PREVIEWED`, `DEMO_REVIEW_RECORDED`, and `DEMO_DISPOSITION_EXECUTED`. The demo reviewer identity remains an explicitly unverified demo reference, as designed.

### Proven root cause of the earlier failures

Earlier instances passed the literal string `input.ValidateInput__output__corporateActionPdf` to Analyze Files and failed with `AGENT_RUNTIME.INVALID_ATTACHMENT_ID`. The Flow node had been overwritten with sidecar-style placeholders.

The working contract deliberately uses two representations:

- the Flow node uses direct `$vars` expressions so Maestro resolves the real upstream `JobAttachment` before starting the agent;
- the agent sidecar uses `{{input.*}}` variable tokens required by agent validation.

Instance `a99ae4d3-242d-43fc-bf92-eead087dbbc3` proves that the corrected direct-expression binding delivered the real PDF to Analyze Files.

## Phase B — automated retrieval implemented locally

The portal still sends only `transferId`, `executionRequestId`, and `enableIXP=false`. It does not upload a document.

The Flow now uses this sequence when the Manual Trigger did not already supply a file:

1. Create the existing isolated demo run.
2. Call the new `TransferIQ_Document_Retrieval` API Workflow with that `runId` and `transferId`.
3. Read run-scoped document metadata and select a READY, non-evaluation `CORPORATE_ACTION_NOTICE` PDF.
4. Fetch its run-scoped base64 content through the TransferIQ API.
5. Validate document identity, transfer ownership, media type, byte size, checksum, and base64 shape.
6. Convert the content to a real UiPath job attachment with `$helpers.file.base64ToFile`.
7. Pass the attachment to the same `TransferInvestigationAgent` and Analyze Files tool.
8. If retrieval is unavailable, invalid, corrupt, or unsupported, record an explicit unavailable reason and continue through the existing `API_ONLY` route.

No URL string is passed where a file is required. No document bytes, signed URLs, API keys, webhook headers, capabilities, or portal access codes are exposed in the Flow result.

### Backend endpoint

The new anonymous-demo endpoint is:

```http
GET /api/demo/runs/{runId}/documents/{documentId}/content
```

It is scoped to the existing isolated run, allowlisted synthetic transfer, and existing sample document. It reuses repository integrity checks and returns bounded base64 content plus metadata and checksum with `Cache-Control: no-store`. Cross-run document access returns 404. Private document APIs remain protected by `X-API-Key`.

### UiPath resources

- API Workflow project: `maestro/TransferIQ_Reconciliation/TransferIQ_Document_Retrieval/`
- Solution API resource: `resources/solution_folder/process/api/TransferIQ_Document_Retrieval.json`
- Existing Flow: `TransferIQ_Reconciliation`
- Existing agent: `TransferInvestigationAgent`
- Built-in tool: `uipath.agent.resource.tool.builtin.analyzefiles`

The canonical Flow contains 81 nodes and 86 edges. Its product validation result is `Valid`.

## Files changed

- `backend/api/demo_execution.py`
- `tests/test_demo_execution.py`
- `tests/test_judging.py`
- `tests/test_step11_agent_documents.py`
- `scripts/maestro-local-runner.mjs`
- `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation.uipx`
- `maestro/TransferIQ_Reconciliation/TransferIQ_Document_Retrieval/*`
- `maestro/TransferIQ_Reconciliation/resources/*/TransferIQ_Document_Retrieval.json`
- `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk/TransferIQ_Reconciliation.flow.ts`
- `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk/finalize-agent-contract.mjs`
- `maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk/prepare-investigation-context.js`
- canonical `TransferIQ_Reconciliation.flow` and its agent sidecar

The Manual Trigger, webhook trigger, Quick Form, decision branches, audit calls, IXP placeholder, and financial rules were not replaced.

## Verification performed

### Live UiPath verification

Phase A is proven by the real instance above. The job logs demonstrate actual Analyze Files activity and PDF retrieval. No mocked extraction is being presented as live evidence.

The Phase B API Workflow is installed and active in UiPath solution version 1.1.0. Portal request `PEX-13e348fd5f1a4e87884e4abfa866d21b` executed it successfully and therefore also production-verified the matching Render metadata/content endpoints. The Flow stopped at agent startup before Analyze Files because of the attachment metadata type mismatch documented below, so automated analysis is not yet accepted end to end.

### First portal Phase B run — bounded failure

| Item | Actual result |
|---|---|
| PEX | `PEX-13e348fd5f1a4e87884e4abfa866d21b` |
| Flow instance | `7864b5c0-f881-4bd1-91fa-197a0f800733`, package 1.1.0 |
| API Workflow | `TransferIQ_Document_Retrieval@1.1.0` — completed |
| Document | `DOC-be94ea38-bd83-4d14-b03b-af83c8322348`, `CORPORATE_ACTION_NOTICE`, PDF |
| Retrieval | `AVAILABLE`; metadata, content, checksum, base64 conversion, and attachment return completed |
| Agent | Failed at startup with `AGENT_STARTUP.INPUT_VALIDATION_ERROR` |
| Downstream | Analyze Files, plan preview, Quick Form, decision, disposition, and final audit did not run |

The API Workflow returned a genuine job attachment whose metadata contained `Size: 2627` as an integer. The deployed agent input schema defined `Metadata.additionalProperties` as strings, so startup rejected `agentDocument.Metadata.Size` before the LLM or Analyze Files tool could run. This is the Agents input-schema-validation playbook's Variant B: the caller payload and declared input schema disagree on a field type.

The deterministic reconciliation completed safely before that failure. SEC-103 remained explained by `CA-2026-081`; SEC-104 remained unresolved at expected 120 versus staged 100, difference `-20`. No plan or decision was created, `correctionsApplied=0`, `transferCompleted=false`, and positions remained unchanged.

The correction is limited to the API Workflow response boundary. `TransferIQ_Document_Retrieval` now returns the same real `JobAttachment` ID, filename, MIME type, and bytes while converting each metadata value to its canonical string representation. For example, the provider-generated integer `Size: 2627` becomes `Size: "2627"`. The canonical agent `JobAttachment` schema remains unchanged, and the Flow still binds the API Workflow file output directly to the existing agent input. Retrieval logic, prompt, evidence validation, reconciliation, Quick Form, webhook, and financial rules are unchanged.

### Local and product verification

- `uip api-workflow validate ...` — Valid.
- `uip api-workflow build ...` — Success.
- Canonical `uip maestro flow validate ... --output json` — Valid.
- Inline `TransferInvestigationAgent` validation — Valid; Analyze Files resource present.
- Post-fix focused Step 11/demo/Maestro suite — **125 passed**, zero failures/errors/skips, 30.496 seconds.
- Post-fix complete suite — **478 passed**, zero failures/errors/skips, 152.554 seconds, with the existing Starlette/httpx deprecation warning.
- Backend document endpoint tests — 13 passed.
- Focused Step 11/demo/graph tests — 22 passed.
- Step 8/9/11 rerun after fallback correction — 65 passed.
- Affected backend/Maestro regression — 267 passed, one existing Starlette/httpx deprecation warning.
- Final complete suite: `python -m pytest -q --tb=short` — **478 passed**, one existing warning, 132.63 seconds.

An earlier complete run produced 477 passed and one failed security-inventory assertion because the intentional new anonymous-demo route was not yet in the explicit public allowlist. The allowlist was corrected, its targeted test passed, and the complete suite above then passed. That failed run is not counted as success.

The local runner uses an explicit test double for the API Workflow and defaults it to `UNAVAILABLE`; it does not fabricate file-analysis success.

The Flow SDK source checker still reports pre-existing brownfield reconstruction diagnostics around the manually authored Quick Form. The installed canonical Flow itself product-validates as `Valid` with no warnings. A candidate Flow-side metadata conversion was rejected because product validation warned that the expression was not a file, so it was not installed. The canonical Flow artifact was left unchanged.

## UiPath deployment — 2026-11-13 UTC

The solution was refreshed, packed, published, and upgraded in place using the UiPath Solution CLI.

- Local manifest projects: `TransferIQ_Reconciliation` (`Flow`) and `TransferIQ_Document_Retrieval` (`Api`).
- Resource refresh: Success; three existing resources retained. The known `Connection ImplicitConnection not found in Resource Catalog` advisory remained unchanged.
- Packed artifact: `TransferIQ-AI_1.1.0.zip`, 136,987 bytes.
- Package SHA-256: `44A6D17404E0C0E74C032255010D242B61F4666C1EB665C8F100208A9F9EF396`.
- Package contents include both project NuGet packages, both process resources, and the existing HTTP Webhook connection resource.
- Publish: Success; package version key `66fc990e-979e-4864-8156-72d1709e3666`.
- In-place upgrade: `VersionChange` from 1.0.1 to 1.1.0.
- Pipeline deployment: `dc11e7df-4f68-490a-b3c3-08df40c858d6`.
- Current deployment key: `6fbd4477-dbce-4713-88c6-e39f780ca6c5`.
- Stable install deployment key: `f65f12c0-511a-4a7e-b8d8-a21a6e9568e3`.
- Deployment status: `SuccessfulActivate`; activation status: `Active` in `DemoFolder`.
- Package status after verification: version 1.1.0 `Active`, with no upgradeable deployment remaining.

No business Flow execution was launched during deployment. Application tests were not rerun after this packaging-only operation; the latest complete application result remains 478 passed as recorded above.

### Metadata fix deployment — solution 1.1.1

- Changed project: `TransferIQ_Document_Retrieval/Workflow.json`; the response keeps the real attachment and string-normalizes only `Metadata` values.
- Contract test updated: `tests/test_step11_agent_documents.py` verifies the packaged workflow contains the normalization.
- Resource refresh: Success; zero created/imported, three retained, zero pruned. The existing `ImplicitConnection` catalog advisory is unchanged.
- Packed artifact: `TransferIQ-AI_1.1.1.zip`, 136,935 bytes.
- Package SHA-256: `99A43BDD7314400DC644EE5F9A79C40B712771E76AA793134964F24ECAACDBDA`.
- Package inspection confirmed both `TransferIQ_Document_Retrieval` and `TransferIQ_Reconciliation`, plus both process resources and the existing webhook connection resource.
- Nested API package inspection confirmed the deployed `Workflow.json` contains both the metadata mapping and `String(value)` conversion.
- Publish: Success; package version key `82c69f87-4bba-4d33-ac75-f0ae1460e5e0`.
- In-place upgrade: `VersionChange` from 1.1.0 to 1.1.1.
- Pipeline deployment: `20dae121-1fb8-4adc-b3c8-08df40c858d6`.
- Current deployment key: `75f527d5-a4d3-47f8-bc17-b404d0a1c982`.
- Stable install deployment key: `f65f12c0-511a-4a7e-b8d8-a21a6e9568e3`.
- Upgrade result: `DeploymentSucceeded / SuccessfulActivate`.
- Post-upgrade inventory: package/current version `1.1.1 / 1.1.1`, operation `Successful`, activation `Active`.

### Post-fix no-upload portal acceptance — 2026-11-13

Portal request `PEX-f260efcbaaf04b52ab97bb693da1f922` executed the active 1.1.1 deployment without a manual file upload.

| Item | Actual result |
|---|---|
| Flow instance | `de4d8ce5-076f-4ee0-90b0-3058514257d0`, package 1.1.1, Completed, no incidents |
| Demo run | `DEMO-2c8c963b60b047efbbf993fbbb4d6a4f` |
| API Workflow document | `DOC-dd25eb90-af4b-47e8-9895-38dc14260644`, `CORPORATE_ACTION_NOTICE`, `application/pdf`, `AVAILABLE` |
| Attachment contract | `Metadata.Size="2627"`, `Metadata.Encoding="byte-array"`; agent startup accepted the file |
| Agent job | `2b79ee78-c174-4311-92ba-826348a6291c`, Serverless, Successful |
| Analyze Files | Real `Tool call - Analyze_Files` and `Analyze_Files` spans completed successfully; attachment metadata and PDF download requests returned HTTP 200 |
| Quick Form | Task `100314822`, completed with Approve and comment `approved` |
| Resolution plan | `PLAN-e8981354-39c2-42c8-af60-6586852fda8f`, `EXECUTED` |
| Final result | `REVIEWED_WITH_OPEN_EXCEPTIONS` / `VERIFIED_DEMO_STATE` |

Analyze Files extracted `SEC-103`, `STOCK_SPLIT`, ratio `2:1`, effective date `2026-08-10`, notice date `2026-08-15`, and evidence reference `CA-2026-081`. The agent correctly labelled its own extraction `NOT_VALIDATED`. The deterministic Flow validator independently compared those fields with the corporate-action API and promoted the structured document evidence to `VERIFIED`, with empty discrepancies and missing fields.

The validated investigation had no missing evidence. SEC-103 was proposed and recorded as `ACCEPT_VERIFIED_EXPLANATION / ACKNOWLEDGED`. SEC-104 was proposed and recorded as `ESCALATE_TO_TRANSFER_OPERATIONS / OPEN_ESCALATED`; expected quantity remained 120, receiving quantity 100, difference `-20`, and resolution status `UNRESOLVED`.

Bounded production reads returned HTTP 200 for the executed plan, audit, and reconciliation. The audit contains exactly `PLAN_PREVIEWED`, `DEMO_REVIEW_RECORDED`, and `DEMO_DISPOSITION_EXECUTED`; the execution event records `positionsChanged=false`. Final verification reports `positionsUnchanged=true`, `transferCompleted=false`, and `correctionsApplied=0`.

Runtime variables and logs were sanitized locally: review capabilities and signed attachment URLs were redacted, and trace payload attributes were removed while retaining correlated span names, statuses, timestamps, and job identifiers.

## Post-fix rejection and CLEAN controls — 2026-11-13 UTC

Both remaining controls were executed once against active solution 1.1.1 and independently inspected through UiPath runtime state and bounded production reads.

### Portal rejection

Portal request `PEX-6cff39d5bba245f386157c2c76263229` correlated to Flow instance `9ce7b7cd-1086-4db4-9590-a9fee5a04ca3`, package 1.1.1. The instance completed with zero incidents. Demo run `DEMO-ac0ef880d3d0475fb3e56f0dcfe9ed97` retrieved the corporate-action PDF and ran agent job `175a2785-d544-44de-972c-68330c445b9f`. Correlated traces contain successful `Tool call - Analyze_Files` and `Analyze_Files` spans.

The agent extracted `SEC-103`, `STOCK_SPLIT`, ratio `2:1`, effective date `2026-08-10`, notice date `2026-08-15`, and evidence reference `CA-2026-081` from document `DOC-6375ddb6-c00c-4c42-b06f-b673c6b8f4d0`. It labelled that extraction `NOT_VALIDATED`; deterministic `ValidateInvestigation` independently promoted it to `VERIFIED`, with no missing evidence or discrepancies.

Quick Form task `100315016` completed with **Reject** and comment `Rejected for Step 11 validation`. Plan `PLAN-e6251613-02d9-487e-a0f8-4cfcc30a1e75` reached `REJECTED`. Bounded production GETs returned HTTP 200 for the plan, audit, verification, and reconciliation.

The audit contains exactly `PLAN_PREVIEWED`, `DEMO_REVIEW_RECORDED`, and `DEMO_DISPOSITION_REJECTED`. Final verification returned `REVIEW_REJECTED / VERIFIED_DEMO_STATE`, `humanReviewOutcome=REJECT`, `positionsUnchanged=true`, and `transferCompleted=false`. SEC-104 remained `UNRESOLVED` at expected 120 versus receiving 100, difference `-20`. No financial correction or position change was applied.

### CLEAN control

Portal request `PEX-3a66c61996514c55bafbae3517f8ef56` correlated to Flow instance `ab6e29d9-1be6-40f2-a236-108c2b721d41`, package 1.1.1, and demo run `DEMO-5680a0a5bbff49f7895b35794ee0db43`. The instance completed with zero incidents and `workflowOutcome=CLEAN`.

The executed-node inventory confirms that document retrieval, `TransferInvestigationAgent`, resolution-plan preview, and Quick Form did not run. The production reconciliation GET returned HTTP 200 with `RECONCILED / COMPLETED`, seven directly matched positions, zero exceptions, and zero differences. This confirms the CLEAN branch avoids unnecessary document analysis and human review.

Runtime variable exports for both controls were sanitized locally: webhook headers, review capabilities, and URLs were redacted before retention.

## Remaining blocker

There is no Step 11 Phase A, Phase B, approval, rejection, CLEAN-control, backend retrieval, metadata-contract, packaging, activation, or solution-resource blocker. The earlier portal behavior that can retain a failed request as active until its configured server timeout is a separate portal recovery hardening item; it did not affect these completed controls.

No application code changed during this final runtime verification, so no new local pytest run was performed. The latest executed local results remain 125 focused tests passed and 478 complete-suite tests passed, as recorded above.
