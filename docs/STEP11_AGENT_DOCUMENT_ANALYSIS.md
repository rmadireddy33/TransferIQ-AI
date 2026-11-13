# Step 11 — Autonomous Agent document evidence analysis

Status: **Phase A is live-verified with a genuine UiPath Analyze Files invocation. Phase B automated retrieval is implemented, locally tested, and product-validated, but is not deployed or live-verified.**

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

The Phase B API Workflow has not been executed in UiPath, and no portal-triggered Phase B run has been launched. The production Render deployment therefore does not yet prove automated retrieval.

### Local and product verification

- `uip api-workflow validate ...` — Valid.
- `uip api-workflow build ...` — Success.
- Canonical `uip maestro flow validate ... --output json` — Valid.
- Backend document endpoint tests — 13 passed.
- Focused Step 11/demo/graph tests — 22 passed.
- Step 8/9/11 rerun after fallback correction — 65 passed.
- Affected backend/Maestro regression — 267 passed, one existing Starlette/httpx deprecation warning.
- Final complete suite: `python -m pytest -q --tb=short` — **478 passed**, one existing warning, 132.63 seconds.

An earlier complete run produced 477 passed and one failed security-inventory assertion because the intentional new anonymous-demo route was not yet in the explicit public allowlist. The allowlist was corrected, its targeted test passed, and the complete suite above then passed. That failed run is not counted as success.

The local runner uses an explicit test double for the API Workflow and defaults it to `UNAVAILABLE`; it does not fabricate file-analysis success.

## Deployment and bounded acceptance

Phase B requires both Render and UiPath deployment. Deploy in this order:

1. Deploy the current backend to Render so the new run-scoped content endpoint exists.
2. Verify `/health`, `/openapi.json`, and one bounded content request against an isolated demo run. Do not expose document content in logs.
3. Pack and publish a new solution version; do not overwrite deployed 1.0.1 without a version bump.
4. Deploy/upgrade the solution and confirm both `TransferIQ_Document_Retrieval` and `TransferIQ_Reconciliation` are active with their real solution resources.
5. Run one portal-triggered TRF-1002 investigation.
6. Inspect the API Workflow job, the Analyze Files tool invocation/output, the Quick Form, plan, verification, and audit for that same PEX correlation.
7. Confirm SEC-103 is independently verified, SEC-104 remains `-20`, positions are unchanged, and the portal reports the persisted final state.
8. Run the rejection and CLEAN controls once each only after the first automated retrieval succeeds.

Do not repeatedly retry an identical failure. `PORTAL_INVESTIGATION_ENABLED`, webhook configuration, IXP defaults, and financial reconciliation rules require no Step 11 change.

## Remaining blocker

There is no remaining Phase A blocker. Phase B acceptance is blocked only by deployment and one bounded real UiPath execution of the new API Workflow path. Until that occurs, automated retrieval must be described as locally implemented and validated, not live-proven.
