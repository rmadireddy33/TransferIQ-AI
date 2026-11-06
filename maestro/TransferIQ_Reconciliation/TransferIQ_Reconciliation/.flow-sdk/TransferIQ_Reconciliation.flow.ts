import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { flow, manual, http, script, inlineAgent, types, out, v, js } from '@uipath/maestro-builder-sdk';

// Public synthetic run APIs use Manual authentication with no credentials or bindings.
const root = fileURLToPath(new URL('.', import.meta.url));
const code = (name: string) => readFileSync(root + 'scripts/' + name + '.js', 'utf8');
const config = existsSync(root + 'runtime.local.json') ? JSON.parse(readFileSync(root + 'runtime.local.json', 'utf8')) : {};
if (Object.keys(config).some(k => k !== 'backendBaseUrl')) throw new Error('Only backendBaseUrl belongs in runtime.local.json');
const baseUrl = config.backendBaseUrl || 'https://transferiq-api.onrender.com';
if (!/^https:\/\/[^/?#@\s]+(?:\/[^?#\s]*)?$/.test(baseUrl)) throw new Error('Cloud runtime requires an HTTPS backend URL');
const path = (suffix: any) => js`${v('backendBaseUrl')} + ${suffix}`;
const request = (method: 'GET' | 'POST', url: any, returns: any, query?: any, body: any = '{}') => http({
  managed: true, method, url: path(url), returns, query,
  timeout: 'PT30S', retryCount: 1,
  headers: { Accept: 'application/json', 'Idempotency-Key': out('ValidateInput', 'correlationId'),
    ...(method === 'POST' ? { 'Content-Type': 'application/json' } : {}) },
  ...(method === 'POST' ? { body, contentType: 'application/json' } : {}),
});
const failure = (stage: string, errorCode: string, summary: string) => js`({
  transferId: $vars.StartTransferInvestigation.output.transferId || null,
  reconciliationRunId: null, totalPositions: null, directlyMatched: null,
  evidenceExplained: null, unresolvedCount: null, costBasisIssues: null,
  exceptions: [], evidenceReferences: [], workflowOutcome: 'FAILED',
  correlation: { transferId: $vars.StartTransferInvestigation.output.transferId || null, failedStep: ${stage} },
  error: { code: ${errorCode}, summary: ${summary} }
})`;
const httpFailure = (stage: string) => (h: any) => h.return({
  // Designer exposes Error under .error; older managed-HTTP runtimes use .output.
  // Read both defensively without assuming a success-response schema contains status.
  result: js`Object.assign(${failure(stage, 'HTTP_REQUEST_FAILED', 'Backend request failed: check HTTP status, availability, authentication and timeout.')}, { httpStatus: (() => {
    const node = Reflect.get($vars, ${stage});
    const status = node?.error?.status ?? (node && Reflect.get(node, 'output'))?.status;
    return Number.isInteger(status) && status >= 100 && status <= 599 ? status : null;
  })() })`,
}, { name: stage + 'Failed' });
const invalid = (stage: string) => (h: any) => h.return({
  result: failure(stage, 'INVALID_RESPONSE', 'Response is missing, malformed, empty where required, truncated, or inconsistent with the requested transfer.'),
}, { name: stage + 'Failed' });

// This is an explicit configuration stop, NOT an extractor or successful mock.
// Replace this Script in Studio Web with Document > Extract > Extract document
// (new model in this Flow), retaining its ID and outgoing success/error edges.
// CLI 1.205 cannot provision that model. Never invent deployment identifiers.
const extractionUnavailable = (reason: string, outcome = 'EVIDENCE_REVIEW_REQUIRED') => js`({
  ...$vars.NormalizeReconciliation.output, workflowOutcome: 'INVESTIGATION_REVIEW_REQUIRED', documentEvidenceStatus: 'IXP_SETUP_OR_EVIDENCE_REQUIRED', humanReviewRequired: true, evidenceOutcome: ${outcome},
  extractionResult: {
    transferId: $vars.NormalizeReconciliation.output.transferId,
    documentType: 'CORPORATE_ACTION_NOTICE', extractedFields: {}, evidenceReference: null,
    validationStatus: 'REVIEW_REQUIRED', discrepancies: [${reason}], extractionStatus: 'EXTRACTION_FAILED'
  }
})`;
const extractionError = (reason: string, name: string) => (h: any) => h.return({
  result: extractionUnavailable(reason),
}, { name, label: 'Evidence Review Required' });

const review = (stage: string, code: string) => js`({
  ...$vars.NormalizeReconciliation.output, workflowOutcome: 'INVESTIGATION_REVIEW_REQUIRED',
  documentEvidenceStatus: $vars.StartTransferInvestigation.output.enableIXP === true ? 'IXP_SETUP_OR_EVIDENCE_REQUIRED' : 'NOT_PROCESSED_IXP_DISABLED',
  investigationStatus: ${code}, investigationSummary: 'Investigation could not be validated; human review is required.',
  findings: [], recommendedNextActions: ['REQUEST_ADDITIONAL_EVIDENCE'], humanReviewRequired: true,
  unresolvedExceptions: $vars.NormalizeReconciliation.output.exceptions.filter(e => e.resolutionStatus !== 'EXPLAINED'),
  unresolvedQuestions: [],
  correctionsApplied: 0, transferCompleted: false, error: { code: ${code}, failedStep: ${stage} }
})`;
const continueAfterReferenceFailure = (name: string, next: string) => (h: any) => h
  .step(name + 'Unavailable', script({ code: "return {status: 'REFERENCE_REQUEST_FAILED'};", returns: 'object' }))
  .stepToRef(next);

export default flow('fa7de741-ad8f-441f-8f3d-9bf96e5f3497')
  .schemaVersion('1.9').name('TransferIQ_Reconciliation')
  .trigger(manual(), { label: 'StartTransferInvestigation' })
  .triggerId('StartTransferInvestigation')
  .input({ transferId: types.string, enableIXP: { type: types.boolean, default: false, description: 'Enable configured IXP evidence path; disabled by default.' }, corporateActionPdf: {
    type: types.file, default: null, description: 'Optional real corporate-action PDF. Missing evidence never clears an exception.'
  } }).output({ result: types.object })
  .var('backendBaseUrl', types.string, baseUrl)
  .step('ValidateInput', script({ code: code('validate-input'), returns: { transferId: 'string', correlationId: 'string' } }))
  .onError((h) => h.return({ result: failure('ValidateInput', 'INVALID_TRANSFER_INPUT', 'Provide a nonempty transferId using letters, digits, hyphens or underscores (maximum 64 characters).') }, { name: 'InvalidInput' }))
  .step('CreateDemoRun', request('POST', '/api/demo/runs', {
    runId: 'string', transferId: 'string', expiresAt: 'number', fictionalDemo: 'boolean', evidenceMode: 'string',
  }, undefined, js`JSON.stringify({ transferId: $vars.ValidateInput.output.transferId })`))
  .onError(httpFailure('CreateDemoRun'))
  .step('ValidateDemoRun', script({ code: code('validate-demo-run'), returns: 'object' }))
  .onError(invalid('ValidateDemoRun'))
  .step('GetTransferDetails', request('GET', js`'/api/demo/runs/' + encodeURIComponent($vars.ValidateDemoRun.output.runId) + '/transfer'`, {
    transferId: 'string', clientId: 'string', deliveringFirmId: 'string', receivingFirmId: 'string', sourceAccountId: 'string', destinationAccountId: 'string', status: 'string', transferType: 'string',
  }))
  .onError(httpFailure('GetTransferDetails'))
  .step('ValidateTransfer', script({ code: code('validate-transfer'), returns: 'object' }))
  .onError(invalid('ValidateTransfer'))
  .step('GetDeliveringPositions', request('GET', js`'/api/demo/runs/' + encodeURIComponent($vars.ValidateDemoRun.output.runId) + '/delivering/accounts/' + encodeURIComponent($vars.ValidateTransfer.output.sourceAccountId) + '/positions'`, {
    items: 'array', total: 'number', limit: 'number', offset: 'number',
  }, { limit: '100', offset: '0' }))
  .onError(httpFailure('GetDeliveringPositions'))
  .step('ValidateDeliveringPositions', script({ code: code('validate-delivering'), returns: 'object' }))
  .onError(invalid('ValidateDeliveringPositions'))
  .step('GetReceivingPositions', request('GET', js`'/api/demo/runs/' + encodeURIComponent($vars.ValidateDemoRun.output.runId) + '/receiving/accounts/' + encodeURIComponent($vars.ValidateTransfer.output.destinationAccountId) + '/positions'`, {
    items: 'array', total: 'number', limit: 'number', offset: 'number', positionKind: 'string', settledHoldings: 'boolean',
  }, { limit: '100', offset: '0' }))
  .onError(httpFailure('GetReceivingPositions'))
  .step('ValidateReceivingPositions', script({ code: code('validate-receiving'), returns: 'object' }))
  .onError(invalid('ValidateReceivingPositions'))
  .step('RunReconciliation', request('POST', js`'/api/demo/runs/' + encodeURIComponent($vars.ValidateDemoRun.output.runId) + '/reconcile'`, {
    transferId: 'string', reconciliationRunId: 'string', status: 'string', executionStatus: 'string', summary: 'object', positions: 'array', exceptions: 'array',
    sourceSnapshotVersion: 'string', targetSnapshotVersion: 'string', inputFingerprint: 'string', ruleVersion: 'string', sourceSnapshotDate: 'string', targetSnapshotDates: 'array',
  }))
  .onError(httpFailure('RunReconciliation'))
  .step('NormalizeReconciliation', script({ code: code('normalize'), returns: {
    transferId: 'string', demoRunId: 'string', reconciliationRunId: 'string', workflowOutcome: 'string',
    totalPositions: 'number', directlyMatched: 'number', evidenceExplained: 'number', unresolvedCount: 'number', costBasisIssues: 'number',
    sourcePositions: 'array', receivingStagingPositions: 'array', costBasisExceptions: 'array', exceptions: 'array', evidenceReferences: 'array',
  } }))
  .onError(invalid('NormalizeReconciliation'))
  .branch('NormalizationFailed', js`$vars.NormalizeReconciliation.output.workflowOutcome === 'FAILED'`,
    yes => yes.label('Invalid reconciliation response').return({ result: out('NormalizeReconciliation') }, { name: 'FailedReconciliation', label: 'FAILED' }),
    no => no.label('Validated reconciliation').branch('RequiresInvestigation', js`$vars.NormalizeReconciliation.output.unresolvedCount > 0 || $vars.NormalizeReconciliation.output.costBasisIssues > 0`,
      investigation => investigation.label('Investigation Required').stepToRef('GetCorporateActionReference'),
      clean => clean.label('Clean Reconciliation').return({ result: js`({ ...$vars.NormalizeReconciliation.output, documentEvidenceStatus: $vars.StartTransferInvestigation.output.enableIXP === true ? 'NOT_REQUIRED' : 'NOT_PROCESSED_IXP_DISABLED' })` }, { name: 'CleanReconciliation', label: 'Clean Reconciliation' })))
  .step('GetCorporateActionReference', request('GET', js`'/api/demo/runs/' + encodeURIComponent($vars.ValidateDemoRun.output.runId) + '/corporate-actions'`, {
    runId: 'string', transferId: 'string', fictionalDemo: 'boolean', referenceSource: 'string',
    items: 'array', total: 'number', limit: 'number', offset: 'number',
  }, { limit: '100', offset: '0' }))
  .onError(continueAfterReferenceFailure('CorporateActionReference', 'IXPEnabled'))
  .branch('IXPEnabled', js`$vars.StartTransferInvestigation.output.enableIXP === true`,
    enabled => enabled.label('Optional IXP enabled').branch('HasCorporateActionPdf', js`$vars.StartTransferInvestigation.output.corporateActionPdf != null`,
      withFile => withFile.label('PDF supplied')
        .step('CorporateActionExtractor', script({ code: "throw new Error('IXP_MODEL_SETUP_REQUIRED: replace this explicit setup stop with a configured Extract document node; see docs/IXP_STEP7_SETUP.md');", returns: 'object' }), { label: 'IXP setup required - replace with Extract document' })
        .onError(extractionError('IXP_EXTRACTION_FAILED_OR_NOT_CONFIGURED', 'ExtractionFailed'))
        .step('ValidateCorporateAction', script({ code: code('validate-corporate-action'), returns: 'object' }))
        .onError(extractionError('EVIDENCE_VALIDATION_FAILED', 'EvidenceValidationFailed'))
        .branch('CorporateActionVerified', js`$vars.ValidateCorporateAction.output.extractionResult.validationStatus === 'VERIFIED'`,
          verified => verified.label('Verified document evidence').stepToRef('GetInvestigationReferences'),
          invalid => invalid.label('Document evidence needs review').return({ result: extractionUnavailable('EVIDENCE_NOT_VERIFIED') }, { name: 'EvidenceReviewRequired' })),
      missing => missing.label('No PDF supplied').return({ result: extractionUnavailable('MISSING_PDF', 'EVIDENCE_UNAVAILABLE') }, { name: 'EvidenceUnavailable' })),
    disabled => disabled.label('IXP disabled - use brokerage APIs'))
  .step('GetInvestigationReferences', request('GET', js`'/api/demo/runs/' + encodeURIComponent($vars.ValidateDemoRun.output.runId) + '/investigation-references'`, {
    contractVersion: 'string', runId: 'string', transferId: 'string', fictionalDemo: 'boolean',
    securities: 'array', identifierMappings: 'array', costBasis: 'array',
  }))
  .onError(continueAfterReferenceFailure('InvestigationReferences', 'PrepareInvestigationContext'))
  .step('PrepareInvestigationContext', script({ code: code('prepare-investigation'), returns: {
    contractVersion: 'string', transferId: 'string', reconciliationRunId: 'string', transfer: 'object',
    deliveringPositions: 'array', receivingStagingPositions: 'array', reconciliation: 'object', reconciliationSummary: 'object', exceptions: 'array',
    securityIdentifiers: 'array', securities: 'array', corporateActions: 'array', identifierMappings: 'array', costBasis: 'array', costBasisExceptions: 'array',
    evidenceRecords: 'array', evidenceReferences: 'array', missingEvidence: 'array', verifiedDocumentEvidence: 'object', documentEvidenceStatus: 'string',
  } }))
  .onError(h => h.return({ result: review('PrepareInvestigationContext', 'INVALID_INVESTIGATION_CONTEXT') }, { name: 'InvestigationContextFailed' }))
  .step('SerializeInvestigationContext', script({ code: 'return JSON.stringify($vars.PrepareInvestigationContext.output);', returns: 'string' }))
  .onError(h => h.return({ result: review('SerializeInvestigationContext', 'INVALID_INVESTIGATION_CONTEXT') }, { name: 'ContextSerializationFailed' }))
  .step('TransferInvestigationAgent', inlineAgent({
    // Discovered with uip agent model list in this tenant, 2026-11-05.
    model: 'gpt-4.1-2025-04-14',
    systemPrompt: readFileSync(root + 'agent-system-prompt.txt', 'utf8'),
    userPrompt: readFileSync(root + 'agent-user-prompt.txt', 'utf8'),
    inputs: { context: out('SerializeInvestigationContext') },
    returns: { transferId: 'string', investigationSummary: 'string', overallRiskLevel: 'string', findings: 'array',
      unresolvedQuestions: 'array', documentEvidenceStatus: 'string', requiresHumanReview: 'boolean' },
    maxIterations: 3, maxTokenPerResponse: 4096, temperature: 0,
  }))
  .onError(h => h.return({ result: review('TransferInvestigationAgent', 'AGENT_FAILED') }, { name: 'AgentFailed' }))
  .step('ValidateInvestigation', script({ code: code('validate-investigation'), returns: 'object' }))
  .onError(h => h.return({ result: review('ValidateInvestigation', 'INVALID_AGENT_OUTPUT') }, { name: 'AgentValidationFailed' }))
  .return({ result: out('ValidateInvestigation') }, { name: 'InvestigationResult', label: 'Investigation report - no financial changes' })
  .build();
