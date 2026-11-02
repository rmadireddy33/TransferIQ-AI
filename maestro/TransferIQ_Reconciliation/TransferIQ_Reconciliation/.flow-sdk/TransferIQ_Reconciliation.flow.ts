import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { flow, manual, http, script, types, out, v, js, err } from '@uipath/maestro-builder-sdk';

// Credentials belong only in Integration Service. Local settings are ignored by Git.
const root = fileURLToPath(new URL('.', import.meta.url));
const code = (name: string) => readFileSync(root + 'scripts/' + name + '.js', 'utf8');
const config = existsSync(root + 'runtime.local.json') ? JSON.parse(readFileSync(root + 'runtime.local.json', 'utf8')) : {};
const bindings = existsSync(root + 'bindings.json') ? JSON.parse(readFileSync(root + 'bindings.json', 'utf8')).bindings : [];
const bound = ['transferiqHttp', 'transferiqFolder'].every(name => bindings?.some((b: any) =>
  b.name === name && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(b.resourceKey)));
if (Object.keys(config).some(k => k !== 'backendBaseUrl')) throw new Error('Only backendBaseUrl belongs in runtime.local.json');
if (bindings.length && !bound) throw new Error('Both verified connection and folder bindings are required');
const baseUrl = config.backendBaseUrl || 'http://localhost:8000';
if (bound && !/^https:\/\/[^/?#@\s]+(?:\/[^?#\s]*)?$/.test(baseUrl)) throw new Error('Cloud binding requires an HTTPS backend URL');
const connection = bound ? { connection: 'transferiqHttp', folder: 'transferiqFolder' } : {};
const path = (suffix: any) => bound ? suffix : js`${v('backendBaseUrl')} + ${suffix}`;
const request = (method: 'GET' | 'POST', url: any, returns: any, query?: any) => http({
  managed: true, ...connection, method, url: path(url), returns, query,
  timeout: 'PT30S', retryCount: 1,
  headers: { Accept: 'application/json', 'X-Correlation-ID': out('ValidateInput', 'correlationId') },
  ...(method === 'POST' ? { body: '{}', contentType: 'application/json' } : {}),
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
  result: js`Object.assign(${failure(stage, 'HTTP_REQUEST_FAILED', 'Backend request failed: check HTTP status, availability, authentication and timeout.')}, { httpStatus: ${err(stage, 'status')} || null })`,
}, { name: stage + 'Failed' });
const invalid = (stage: string) => (h: any) => h.return({
  result: failure(stage, 'INVALID_RESPONSE', 'Response is missing, malformed, empty where required, truncated, or inconsistent with the requested transfer.'),
}, { name: stage + 'Failed' });

export default flow('fa7de741-ad8f-441f-8f3d-9bf96e5f3497')
  .schemaVersion('1.9').name('TransferIQ_Reconciliation')
  .trigger(manual(), { label: 'StartTransferInvestigation' })
  .triggerId('StartTransferInvestigation')
  .input({ transferId: types.string }).output({ result: types.object })
  .var('backendBaseUrl', types.string, baseUrl)
  .var('backendConnectionConfigured', types.boolean, bound)
  .step('ValidateInput', script({ code: code('validate-input'), returns: { transferId: 'string', correlationId: 'string' } }))
  .onError((h) => h.return({ result: failure('ValidateInput', 'INVALID_TRANSFER_INPUT', 'Provide a nonempty transferId using letters, digits, hyphens or underscores (maximum 64 characters).') }, { name: 'InvalidInput' }))
  .branch('BackendConfigured', v('backendConnectionConfigured'),
    yes => yes.label('Secure HTTP connection configured')
      .step('ValidateBackendConfiguration', script({ code: "if (typeof $vars.backendBaseUrl !== 'string' || !/^https:\\/\\//.test($vars.backendBaseUrl)) throw new Error('INVALID_CONFIGURATION'); return true;", returns: 'boolean' }))
      .onError(h => h.return({ result: failure('ValidateBackendConfiguration', 'INVALID_CONFIGURATION', 'A configured cloud connection requires an HTTPS backend URL.') }, { name: 'InvalidConfiguration' })),
    no => no.label('Configuration required').return({ result: failure('BackendConfigured', 'CONFIGURATION_REQUIRED', 'Configure a reachable HTTPS backend and bind its UiPath HTTP connection; localhost is not reachable from UiPath Cloud.') }, { name: 'ConfigurationRequired' }))
  .step('GetTransferDetails', request('GET', js`'/api/transfers/' + encodeURIComponent($vars.ValidateInput.output.transferId)`, {
    transferId: 'string', clientId: 'string', deliveringFirmId: 'string', receivingFirmId: 'string', sourceAccountId: 'string', destinationAccountId: 'string', status: 'string', transferType: 'string',
  }))
  .onError(httpFailure('GetTransferDetails'))
  .step('ValidateTransfer', script({ code: code('validate-transfer'), returns: 'object' }))
  .onError(invalid('ValidateTransfer'))
  .step('GetDeliveringPositions', request('GET', js`'/api/delivering/accounts/' + encodeURIComponent($vars.ValidateTransfer.output.sourceAccountId) + '/positions'`, {
    items: 'array', total: 'number', limit: 'number', offset: 'number',
  }, { limit: '100', offset: '0' }))
  .onError(httpFailure('GetDeliveringPositions'))
  .step('ValidateDeliveringPositions', script({ code: code('validate-delivering'), returns: 'object' }))
  .onError(invalid('ValidateDeliveringPositions'))
  .step('GetReceivingPositions', request('GET', js`'/api/receiving/accounts/' + encodeURIComponent($vars.ValidateTransfer.output.destinationAccountId) + '/positions'`, {
    items: 'array', total: 'number', limit: 'number', offset: 'number', positionKind: 'string', settledHoldings: 'boolean',
  }, { transferId: out('ValidateInput', 'transferId'), limit: '100', offset: '0' }))
  .onError(httpFailure('GetReceivingPositions'))
  .step('ValidateReceivingPositions', script({ code: code('validate-receiving'), returns: 'object' }))
  .onError(invalid('ValidateReceivingPositions'))
  .step('RunReconciliation', request('POST', js`'/api/transfers/' + encodeURIComponent($vars.ValidateInput.output.transferId) + '/reconcile'`, {
    transferId: 'string', reconciliationRunId: 'string', status: 'string', executionStatus: 'string', summary: 'object', positions: 'array', exceptions: 'array',
    sourceSnapshotVersion: 'string', targetSnapshotVersion: 'string', inputFingerprint: 'string', ruleVersion: 'string', sourceSnapshotDate: 'string', targetSnapshotDates: 'array',
  }))
  .onError(httpFailure('RunReconciliation'))
  .step('NormalizeReconciliation', script({ code: code('normalize'), returns: 'object' }))
  .onError(invalid('NormalizeReconciliation'))
  .branch('NormalizationFailed', js`$vars.NormalizeReconciliation.output.workflowOutcome === 'FAILED'`,
    yes => yes.label('Invalid reconciliation response').return({ result: out('NormalizeReconciliation') }, { name: 'FailedReconciliation', label: 'FAILED' }),
    no => no.label('Validated reconciliation').branch('RequiresInvestigation', js`$vars.NormalizeReconciliation.output.unresolvedCount > 0`,
      investigation => investigation.label('Investigation Required').return({ result: out('NormalizeReconciliation') }, { name: 'InvestigationRequired', label: 'Investigation Required' }),
      clean => clean.label('Clean Reconciliation').return({ result: out('NormalizeReconciliation') }, { name: 'CleanReconciliation', label: 'Clean Reconciliation' })))
  .build();
