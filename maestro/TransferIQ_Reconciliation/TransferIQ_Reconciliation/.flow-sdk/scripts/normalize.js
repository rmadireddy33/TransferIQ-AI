const transferId = $vars.ValidateInput.output.transferId;
const correlationId = $vars.ValidateInput.output.correlationId;
const failed = {
  transferId, reconciliationRunId: null, totalPositions: null, directlyMatched: null,
  evidenceExplained: null, unresolvedCount: null, costBasisIssues: null,
  exceptions: [], evidenceReferences: [], workflowOutcome: 'FAILED',
  correlation: { correlationId, transferId, failedStep: 'NormalizeReconciliation' },
  error: { code: 'INVALID_RECONCILIATION_RESPONSE', summary: 'Reconciliation response is incomplete, malformed or inconsistent.' }
};
const response = $vars.RunReconciliation.output;
const httpStatus = response && (Reflect.get(response, 'code') ?? Reflect.get(response, 'statusCode'));
const body = response && response.body;
const object = x => x && typeof x === 'object' && !Array.isArray(x);
const text = x => typeof x === 'string' && x.length > 0;
const strings = x => Array.isArray(x) && x.every(text);
const quantity = x => x === null || (typeof x === 'string' && /^-?\d+(\.\d+)?$/.test(x));
if (!response || ![200, 201].includes(httpStatus) || !object(body) || body.transferId !== transferId ||
    !text(body.reconciliationRunId) || body.executionStatus !== 'COMPLETED' ||
    !['RECONCILED', 'EXCEPTIONS_DETECTED'].includes(body.status) || !object(body.summary) ||
    !['totalPositions', 'directlyMatched', 'evidenceExplained', 'unresolved', 'costBasisIssues'].every(k => Number.isSafeInteger(body.summary[k]) && body.summary[k] >= 0) ||
    !Array.isArray(body.positions) || !Array.isArray(body.exceptions)) return failed;
const summary = body.summary;
if (summary.totalPositions < 1 || summary.totalPositions !== body.positions.length ||
    summary.totalPositions !== summary.directlyMatched + summary.evidenceExplained + summary.unresolved ||
    body.status !== (summary.unresolved || summary.costBasisIssues ? 'EXCEPTIONS_DETECTED' : 'RECONCILED')) return failed;
if (!body.positions.every(p => object(p) && text(p.securityId) && ['MATCHED', 'EXPLAINED', 'UNRESOLVED'].includes(p.classification) &&
    strings(p.evidenceReferences) && ['sourceQuantity', 'targetQuantity', 'expectedQuantity', 'difference'].every(k => quantity(p[k])) &&
    (p.classification !== 'EXPLAINED' || p.evidenceReferences.length > 0))) return failed;
if (new Set(body.positions.map(p => p.securityId)).size !== body.positions.length ||
    body.positions.filter(p => p.classification === 'MATCHED').length !== summary.directlyMatched ||
    body.positions.filter(p => p.classification === 'EXPLAINED').length !== summary.evidenceExplained ||
    body.positions.filter(p => p.classification === 'UNRESOLVED').length !== summary.unresolved) return failed;
if (!body.exceptions.every(e => object(e) && text(e.exceptionId) && e.transferId === transferId && e.reconciliationRunId === body.reconciliationRunId &&
    (e.securityId === null || text(e.securityId)) && text(e.exceptionType) && text(e.description) && strings(e.evidenceReferences) &&
    ['EXPLAINED', 'UNRESOLVED', 'REQUIRES_INVESTIGATION'].includes(e.resolutionStatus) && e.status === e.resolutionStatus &&
    ['sourceQuantity', 'targetQuantity', 'expectedQuantity', 'normalizedQuantity', 'difference'].every(k => quantity(e[k])))) return failed;
const costBasisExceptions = body.exceptions.filter(e => e.exceptionType.startsWith('COST_BASIS_'));
const positionExceptions = body.exceptions.filter(e => !e.exceptionType.startsWith('COST_BASIS_'));
if (costBasisExceptions.length !== summary.costBasisIssues ||
    positionExceptions.filter(e => e.resolutionStatus === 'EXPLAINED').length !== summary.evidenceExplained ||
    positionExceptions.filter(e => e.resolutionStatus !== 'EXPLAINED').length !== summary.unresolved ||
    new Set(body.exceptions.map(e => e.exceptionId)).size !== body.exceptions.length ||
    !body.positions.every(p => p.classification === 'MATCHED' || positionExceptions.some(e => e.securityId === p.securityId &&
      (p.classification === 'EXPLAINED' ? e.resolutionStatus === 'EXPLAINED' : e.resolutionStatus !== 'EXPLAINED')))) return failed;
const unresolvedExceptions = positionExceptions.filter(e => e.resolutionStatus !== 'EXPLAINED');
const evidenceReferences = Array.from(new Set(body.positions.flatMap(p => p.evidenceReferences).concat(body.exceptions.flatMap(e => e.evidenceReferences)))).sort();
return {
  transferId, reconciliationRunId: body.reconciliationRunId,
  totalPositions: summary.totalPositions, directlyMatched: summary.directlyMatched,
  evidenceExplained: summary.evidenceExplained, unresolvedCount: summary.unresolved,
  exceptions: body.exceptions, workflowOutcome: summary.unresolved > 0 ? 'INVESTIGATION_REQUIRED' : 'CLEAN',
  costBasisIssues: summary.costBasisIssues, costBasisExceptions,
  requiresCostBasisReview: summary.costBasisIssues > 0, quantityReconciliationOnly: true,
  unresolvedExceptions, affectedSecurityIdentifiers: Array.from(new Set(unresolvedExceptions.map(e => e.securityId).filter(text))),
  exceptionClassifications: Array.from(new Set(unresolvedExceptions.map(e => e.exceptionType))), evidenceReferences,
  explanation: summary.unresolved > 0 ? 'Unresolved position exceptions require investigation; no correction was applied.' :
    (summary.costBasisIssues > 0 ? 'Quantities reconcile. Cost-basis evidence still requires separate review.' : 'All positions are directly matched or explained by backend-verified evidence.'),
  transferStatus: $vars.ValidateTransfer.output.status,
  sourcePositions: $vars.ValidateDeliveringPositions.output.items,
  receivingStagingPositions: $vars.ValidateReceivingPositions.output.items,
  positionKind: 'RECEIVING_TRANSFER_STAGING', settledHoldings: false,
  correlation: { correlationId, transferId, reconciliationRunId: body.reconciliationRunId }, error: null
};
