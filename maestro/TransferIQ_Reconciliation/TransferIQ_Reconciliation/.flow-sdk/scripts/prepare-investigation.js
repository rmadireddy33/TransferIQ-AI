// Evidence assembly only. No financial arithmetic, extraction or AI simulation.
const n = $vars.NormalizeReconciliation.output;
const r = $vars.RunReconciliation.output.body;
const object = x => x && typeof x === 'object' && !Array.isArray(x);
const text = x => typeof x === 'string' && x.length > 0;
if (!['INVESTIGATION_REQUIRED', 'CLEAN'].includes(n.workflowOutcome) ||
    r.status !== 'EXCEPTIONS_DETECTED' || !r.exceptions.length) throw new Error('INVALID_INVESTIGATION_CONTEXT');
const missingEvidence = [];
const response = name => Reflect.get($vars, name)?.output;
const ca = response('GetCorporateActionReference');
const refs = response('GetInvestigationReferences');
const scoped = x => object(x) && x.transferId === n.transferId && x.runId === n.demoRunId && x.fictionalDemo === true;
const ok = x => (x?.code ?? x?.statusCode) === 200;
let corporateActions = [], securities = [], identifierMappings = [], costBasis = [];
const securityIds = new Set(r.positions.map(p => p.securityId));
if (ok(ca) && scoped(ca.body) && Array.isArray(ca.body.items) && ca.body.total === ca.body.items.length && ca.body.offset === 0 &&
    ca.body.items.every(a => object(a) && securityIds.has(a.securityId) && text(a.corporateActionId) && typeof a.verified === 'boolean')) {
  corporateActions = ca.body.items;
} else missingEvidence.push({ source: 'corporate-actions', code: 'REFERENCE_UNAVAILABLE_OR_INVALID', httpStatus: ca?.code ?? ca?.statusCode ?? null });
if (ok(refs) && scoped(refs.body) && refs.body.contractVersion === '1.0' &&
    Array.isArray(refs.body.securities) && Array.isArray(refs.body.identifierMappings) && Array.isArray(refs.body.costBasis) &&
    refs.body.securities.every(s => object(s) && securityIds.has(s.securityId)) &&
    refs.body.identifierMappings.every(m => object(m) && securityIds.has(m.canonicalSecurityId) && typeof m.verified === 'boolean') &&
    refs.body.costBasis.every(b => object(b) && b.transferId === n.transferId && securityIds.has(b.securityId))) {
  ({ securities, identifierMappings, costBasis } = refs.body);
} else missingEvidence.push({ source: 'investigation-references', code: 'REFERENCE_UNAVAILABLE_OR_INVALID', httpStatus: refs?.code ?? refs?.statusCode ?? null });
// Index actual record IDs and actual evidence references, scoped by security.
const evidenceRecords = [];
const add = (id, securityId, kind, verified) => {
  if (text(id)) evidenceRecords.push({ evidenceId: id, securityId, kind, verified });
};
for (const p of n.sourcePositions) add(p.positionId, p.securityId, 'SOURCE_POSITION', true);
for (const p of n.receivingStagingPositions) add(p.stagingPositionId, p.securityId, 'RECEIVING_STAGING', true);
for (const e of r.exceptions) add(e.exceptionId, e.securityId, 'RECONCILIATION_EXCEPTION', true);
for (const a of corporateActions) {
  add(a.corporateActionId, a.securityId, 'CORPORATE_ACTION', a.verified);
  add(a.evidenceReference, a.securityId, 'CORPORATE_ACTION', a.verified);
}
for (const m of identifierMappings) {
  add(m.mappingId, m.canonicalSecurityId, 'IDENTIFIER_MAPPING', m.verified);
  add(m.evidenceReference, m.canonicalSecurityId, 'IDENTIFIER_MAPPING', m.verified);
}
for (const b of costBasis) {
  add(b.costBasisId, b.securityId, 'COST_BASIS', b.status === 'COMPLETE');
  add(b.evidenceReference, b.securityId, 'COST_BASIS', b.status === 'COMPLETE');
}
const enabled = $vars.StartTransferInvestigation.output.enableIXP === true;
const verifiedDocument = enabled ? response('ValidateCorporateAction')?.extractionResult : null;
if (enabled && verifiedDocument?.validationStatus !== 'VERIFIED') throw new Error('DOCUMENT_EVIDENCE_NOT_VERIFIED');
return {
  contractVersion: '1.0', transferId: n.transferId, reconciliationRunId: n.reconciliationRunId,
  transfer: $vars.ValidateTransfer.output, deliveringPositions: n.sourcePositions,
  receivingStagingPositions: n.receivingStagingPositions,
  reconciliation: r, reconciliationSummary: r.summary, exceptions: r.exceptions,
  securityIdentifiers: Array.from(securityIds).map(securityId => ({ securityId,
    observedIdentifiers: Array.from(new Set([...n.sourcePositions, ...n.receivingStagingPositions]
      .filter(p => p.securityId === securityId).map(p => p.observedIdentifier).filter(text))) })),
  securities, corporateActions, identifierMappings, costBasis,
  costBasisExceptions: n.costBasisExceptions, evidenceRecords, evidenceReferences: n.evidenceReferences,
  missingEvidence, verifiedDocumentEvidence: verifiedDocument,
  documentEvidenceStatus: enabled ? 'VERIFIED_IXP_EVIDENCE' : 'NOT_PROCESSED_IXP_DISABLED'
};
