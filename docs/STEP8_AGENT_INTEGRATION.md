# Step 8 — Autonomous transfer investigation

The existing Flow now includes a real `uipath.agent.autonomous` node named `TransferInvestigationAgent`. It uses `gpt-4.1-2025-04-14`, returned by the tenant's `uip agent model list --output json` on 2026-11-05 America/New_York. It has no financial mutation tools, escalation resources, or private backend credentials. The original solution and deterministic financial engine are retained.

Real cloud execution has verified the clean branch and TRF-1002/TRF-1004/TRF-1005 agent invocation, input, output and validation. TRF-1002 explained the SEC-103 2-for-1 split and preserved the SEC-104 20-share shortage. Its final outcome is `INVESTIGATION_REVIEW_REQUIRED`: the supplemental reference endpoint has not been deployed to Render and returned 404. The agent itself completed with no output validation errors. See [actual test evidence](STEP8_AGENT_TEST_CASES.md).

## Contracts and data flow

Manual inputs are `transferId: string`, `enableIXP: boolean = false`, and the preserved optional `corporateActionPdf: file = null`. The existing five HTTP operations and reconciliation normalization remain in place. The investigation decision now includes either unresolved quantities **or** separate cost-basis issues. TRF-1001 remains CLEAN without invoking the agent. The backend's calculation, classifications, amounts and positions are unchanged.

After that decision, the Flow fetches `/api/demo/runs/{runId}/corporate-actions`, then `/api/demo/runs/{runId}/investigation-references`. The latter is a new bounded GET returning `contractVersion: "1.0"`, run/transfer IDs, fictional-demo marker, scoped `securities`, `identifierMappings`, and `costBasis`. Decimal values remain strings; absent basis records stay absent. It uses only the run-specific database session, not the private session factory. Each collection is capped at 100 with explicit failure above the cap. Existing run quotas, TTL, no-store headers and allowlisted scenario rules apply. No anonymous correction, approval or upload route is added.

`PrepareInvestigationContext` assembles contract version 1.0 from actual API responses and prior outputs:

- Transfer/run identity and transfer metadata; source and receiving staging records.
- Full reconciliation result, summary, exceptions and cost-basis exceptions.
- Security IDs and observed identifiers; fetched security master, corporate actions, identifier mappings and basis records.
- An evidence index of actual source/staging/exception/reference IDs, security ownership and verification status; original evidence references.
- `missingEvidence` with failed source, reason and available HTTP status; `documentEvidenceStatus`; verified document evidence only when independently validated.

Reference failure handlers rejoin context preparation, preserving available evidence and recording the gap. An unavailable reference never becomes a synthetic successful response. The agent can investigate the remaining evidence; the final report requires review while gaps remain.

`SerializeInvestigationContext` serializes the assembled context. The agent binds directly to that node's output. The SDK emits the runtime input name `SerializeInvestigationContext__output` and rewrites the prompt placeholder to that path. Computed expressions inside inline-agent bindings are avoided because they do not receive a reliable runtime argument.

## Exact prompts and structured response

The exact editable prompts are [system prompt](../maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk/agent-system-prompt.txt) and [user prompt](../maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk/agent-user-prompt.txt). The system prompt includes all 14 requested rules plus the field and controlled-action contract. Compilation produces the real agent sidecar and node together. Do not edit only the generated sidecar.

The SDK supports top-level `string`, `boolean`, `object` and `array` return types, but its `returns` map does not declare nested item properties. `findings` and `unresolvedQuestions` are real arrays, not JSON text. The prompt specifies nested fields; the post-agent Script enforces their exact shape and rejects additional fields. There is no lossy text-to-JSON mapping.

```json
{
  "transferId": "string",
  "investigationSummary": "string",
  "overallRiskLevel": "LOW | MEDIUM | HIGH",
  "findings": [{
    "exceptionId": "string",
    "securityId": "string",
    "classification": "exact backend exceptionType",
    "rootCause": "facts, hypotheses and missing evidence",
    "evidenceIds": ["actual provided record/evidence ID"],
    "confidence": "LOW | MEDIUM | HIGH",
    "evidenceStatus": "VERIFIED | INCOMPLETE | CONFLICTING",
    "recommendedAction": "controlled category",
    "requiresHumanReview": true
  }],
  "unresolvedQuestions": ["string"],
  "documentEvidenceStatus": "exact context status",
  "requiresHumanReview": true
}
```

The only recommendation categories are `ACCEPT_VERIFIED_MATCH`, `NORMALIZE_COMPARISON`, `REQUEST_ADDITIONAL_EVIDENCE`, `INVESTIGATE_POSITION_SHORTAGE`, `OPEN_COST_BASIS_CASE`, and `ESCALATE_UNSUPPORTED_CHANGE`. These are advisory data, never permissions. Acceptance/normalization requires an already EXPLAINED backend exception and independently fetched, verified, security-matched corporate-action or mapping evidence. Unresolved root causes cannot become VERIFIED because of agent confidence. Cost-basis findings require separate handling. Conflict requires review. No text matching decides financial safety; prose remains untrusted and is not executed.

The returned report preserves the reconciliation result and adds document status, investigation status/summary, findings, evidence records, missing evidence, validation errors, unresolved exceptions, next actions and `humanReviewRequired`. All accepted findings cover exactly one actual exception, with no duplicates. Unresolved exceptions retain their original records. `correctionsApplied=0` and `transferCompleted=false` describe the Flow's absence of financial mutation capability.

`INVESTIGATION_COMPLETED` means the agent's structured report passed validation with available references; it never means transfer completion or exception resolution. Missing references, conflicts or invalid output produce `INVESTIGATION_REVIEW_REQUIRED`. Model unavailability/timeouts go through `AgentFailed`, preserving reconciliation and setting `investigationStatus=AGENT_FAILED` with workflow outcome `INVESTIGATION_REVIEW_REQUIRED`. Existing CLEAN and FAILED outcomes remain. No financial state transition is added.

## Optional IXP

With `enableIXP=false`, the Flow bypasses `HasCorporateActionPdf`, `CorporateActionExtractor` and document validation, regardless of whether a file was supplied. The context and report explicitly say `NOT_PROCESSED_IXP_DISABLED`. Corporate-action API evidence is available independently of document extraction.

With `enableIXP=true`, absent PDFs or the existing setup-stop produce explicit review/setup-required outcomes. The Script is still not an extractor. No new IXP model was created and no extraction success is claimed. To activate later:

1. Resolve the existing UiPath IXP permission/configuration blocker using [Step 7 setup](IXP_STEP7_SETUP.md).
2. Preserve/download the current solution. Replace the setup-stop with an actual Extract document node and functioning model binding; inspect real provider output before adapting it to the deterministic validator.
3. Preserve the validation/error edges. Only verified output may reach `PrepareInvestigationContext.verifiedDocumentEvidence`.
4. Merge the designer artifact into SDK source before rebuilding. `build-maestro.ps1` deliberately refuses to overwrite a real Extract node with the old setup-stop.
5. Validate and test real extraction, missing/broken model, wrong document ownership, low-confidence and conflicting evidence before enabling the flag.

All Step 8 live runs use `enableIXP=false`.

## Build, debug and evaluate

```powershell
$env:PATH = "$env:APPDATA\npm;$env:PATH"
.\scripts\build-maestro.ps1
.\.venv\Scripts\python.exe -m pytest -q --tb=short
uip solution resources refresh --solution-folder maestro/TransferIQ_Reconciliation --output json
uip maestro flow debug maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation --inputs '@input.json' --timeout 600 --output json
```

`input.json` must be UTF-8 **without BOM**, for example `{"transferId":"TRF-1002","enableIXP":false}`. Debug uploads the existing solution into Studio Web and executes real APIs/model calls. Preserve cloud edits before debugging. Do not launch concurrent debug uploads. The current resource refresh reports `Connection ImplicitConnection not found in Resource Catalog`; the real runs verify that credential-free Manual HTTP works despite this advisory.

Evaluate the saved trace's `PrepareInvestigationContext`, agent inputs/outputs, `ValidateInvestigation`, terminal report and backend positions. The unit harness only uses an explicitly supplied `agentTestDouble`; without it the harness reports agent failure. It never calls or imitates a live model. Existing Flow eval files are not claimed as an executed Step 8 evaluation set. Follow the scenario matrix in [test cases](STEP8_AGENT_TEST_CASES.md) for manual live evaluation.

## Limitations and next step

Deploy this backend revision to the existing Render service so the new supplemental-reference GET is available, then rerun the investigation scenarios. No Render deployment was performed here. IXP remains disabled and permission-blocked. Model prose quality is checked through the observed scenarios; structural validation is not proof that every possible natural-language claim is correct. Runtime invocation failures are handled; no custom timer, cancellation service or unbounded retry loop is introduced. Agent iteration limit is 3, response limit 4096 tokens, temperature 0.

Investigation reports currently live in Maestro results/traces. The backend persists reconciliation/correlation in its existing isolated SQLite run; no new agent-result table, backend dispatcher or outbox is implemented. No Human Quick Forms, financial corrections, settlement, frontend, new database system or new IXP model is included. The workspace has no `.git` repository, so version-control diff/history was unavailable; local and downloaded cloud baselines are retained under ignored `data/verification/step8/`.

Provider references consulted: UiPath's [Autonomous agent](https://docs.uipath.com/maestro-automate/automation-cloud/latest/user-guide/node-agent), [add an AI agent](https://docs.uipath.com/maestro-automate/automation-cloud/latest/user-guide/add-an-ai-agent), and [Extract node](https://docs.uipath.com/maestro-automate/automation-cloud/latest/user-guide/node-extract), plus the installed Maestro Flow SDK signatures and skills.
