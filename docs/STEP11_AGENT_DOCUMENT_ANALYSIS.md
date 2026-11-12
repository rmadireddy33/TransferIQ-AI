# Step 11 — Autonomous Agent document evidence analysis

Status: **Phase A implemented and locally/product validated; real Analyze Files execution is blocked before run creation by UiPath debug authorization. Phase B is intentionally not implemented.**

## Scope and safety boundary

The existing Manual Trigger, `PortalWebhook`, deterministic reconciliation, Quick Form, review ledger, audit, and financial immutability rules remain in place. IXP remains disabled by default. The new route is advisory evidence analysis only:

- `AGENT_ANALYZE_FILES` when the Manual Trigger supplies a genuine file attachment.
- `API_ONLY` when no file is available.
- The legacy `NOT_PROCESSED_IXP_DISABLED` plan value remains accepted for backward-compatible persisted plans.

The agent cannot authorize a quantity change. Extracted document fields are independently compared with the existing corporate-action API by `ValidateInvestigation`. Missing or contradictory fields produce `validationStatus=REVIEW_REQUIRED`. SEC-104 remains governed by the deterministic reconciliation result and cannot be cleared by document extraction.

UiPath's supported Analyze Files contract accepts an `attachments` array of job attachments plus an `analysisTask`; a URL string is not used as a file. Supported file types include PDF. References: [Analyze Files](https://docs.uipath.com/agents/automation-cloud/latest/user-guide/analyze-files) and [Attachments](https://docs.uipath.com/agents/automation-cloud/latest/user-guide/attachments).

## Implemented Phase A

`TransferInvestigationAgent` now has exactly one built-in tool resource:

```text
uipath.agent.resource.tool.builtin.analyzefiles
properties.toolType = analyze-attachments
```

The Manual Trigger's existing `corporateActionPdf` is bound as a `JobAttachment`. When present, the prompt requires one Analyze Files call and requests:

- `securityId`
- `actionType`
- `splitNumerator`
- `splitDenominator`
- `effectiveDate`
- `noticeDate`
- `evidenceReference`

The structured `documentEvidence` result contains `documentId`, `documentType`, `extractedFields`, `sourceEvidenceReference`, `extractionMethod`, `validationStatus`, `discrepancies`, and `missingFields`. A manual attachment may not carry the repository `documentId`; the agent must return null and list it as missing instead of inventing one. Automated metadata retrieval is the Phase B mechanism that will supply this identity.

The validator normalizes only the known document term `STOCK_SPLIT` to the API term `SPLIT`, then compares security, numerator, denominator, effective date, and evidence reference with independently verified corporate-action data. `noticeDate` is extracted but is not represented by the current corporate-action API, so it is not falsely described as API-verified.

## Portal progress correction

The screenshot showed `/portal/transfers/TRF-1002/investigation`, not the persisted PEX progress route. The timeline already lives at `/portal/investigations/{executionRequestId}`. Returning to transfer details dropped the PEX correlation, leaving no route back to the timeline.

The React change now:

- stores the started PEX identifier in session storage for navigation continuity;
- carries `executionRequestId` in the transfer-detail query string;
- shows **View Maestro progress** on the Investigation tab;
- preserves the PEX identifier when returning from the progress page;
- continues to avoid starting a second execution on refresh.

For supplied request `PEX-9a8110c204d8489e882f97a22adaa9c9`, the temporally corresponding UiPath instance `4f958960-139a-48c3-af97-aa8bf2f70ab8` completed on solution 1.0.1. Its executed elements include the agent, `quickForm1`, decision recording, disposition execution, independent verification, audit read, and final report; all reported `Completed`. The instance API did not expose global variables for an exact PEX value comparison, so this is timing-based correlation, not a claimed direct identifier match.

## Validation and tests

Observed local/product results:

- Frontend unit tests: **18 passed**.
- Frontend production build: **successful** (`index-C0vY8r6s.js`, `index-CrogKrPt.css`).
- Focused Step 8/9/10B/11/resolution/Maestro regression: **199 passed**, one existing Starlette/httpx deprecation warning.
- Complete backend suite: **477 passed**, one existing Starlette/httpx deprecation warning, 137.50 seconds.
- Canonical Flow compile delta: **78 nodes / 81 edges**, adding one tool node and one artifact edge.
- Canonical product Flow validation: **Valid**, no warnings.
- Inline agent validation: **Valid**, one resource.

The new Step 11 tests use explicit test doubles and do not prove file extraction. They cover the tool/resource contract, attachment schema, API-only routing, exact independent comparison, missing fields, mismatches, SEC-104 `-20`, and unchanged source/staging positions.

## Real Phase A attempt and blocker

One bounded CLI debug attempt was made with the actual fictional PDF:

```text
mock_documents/generated/primary/TRF-1002/corporate_action_notice-layout1-a4ea1506d5a3.pdf
```

UiPath rejected `prepare-custom-debug` with **HTTP 403 / permission_denied** before a Flow instance was created. No agent job, Analyze Files invocation, task, or output resulted. The identical configuration was not retried.

To complete Phase A, open the updated Flow in Studio Web under an identity permitted to debug the solution, select the Manual Trigger, set `transferId=TRF-1002` and `enableIXP=false`, attach the PDF above to `corporateActionPdf`, and start one run. Inspect the agent trace for a genuine Analyze Files tool call and capture its returned analysis plus `documentEvidence`. If the run reaches the existing Quick Form, complete it normally and verify SEC-104 remains `-20` and positions remain unchanged.

## Phase B gate

Phase B must not begin until the real Phase A trace proves that Analyze Files received and read the file. After that gate:

1. Read run-scoped document metadata from the hosted TransferIQ API.
2. Select the `CORPORATE_ACTION_NOTICE` document and retain its real `documentId`.
3. Download bytes through a supported UiPath file-capable step into a job attachment.
4. Pass that attachment, not its URL, to Analyze Files.
5. Preserve `PortalWebhook`; no portal upload is introduced.
6. Return explicit unavailable/corrupt/unsupported states and fall back to `API_ONLY` without claiming document validation.

No automated document-retrieval node or portal-triggered Step 11 execution has been implemented or claimed.

## Deployment requirements

Do not deploy Step 11 until Phase A is proven in the tenant. After the real trace passes:

1. Rerun the complete backend and frontend suites.
2. Product-validate the canonical Flow again.
3. Refresh solution resources so the built-in tool sidecar is included.
4. Pack/publish a new solution version; do not replace 1.0.1 in place without a version bump.
5. Deploy the Render backend/frontend changes. No new Render secret is required for Phase A.
6. Run one bounded portal acceptance only after Phase B is implemented and validated.

The current local portal and backend changes are not yet deployed to Render, and the UiPath 1.0.1 deployment does not contain Step 11.
