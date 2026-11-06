// Treat model output as untrusted data. This validator never authorizes writes.
const c = $vars.PrepareInvestigationContext.output;
const n = $vars.NormalizeReconciliation.output;
const a = $vars.TransferInvestigationAgent.output;
const object = x => x && typeof x === 'object' && !Array.isArray(x);
const text = x => typeof x === 'string' && x.trim().length > 0 && x.length <= 8000;
const list = x => Array.isArray(x) && x.length <= 100;
const keys = (x, expected) => object(x) && Object.keys(x).length === expected.length && expected.every(k => Object.prototype.hasOwnProperty.call(x,k));
const levels = ['LOW','MEDIUM','HIGH'];
const actions = ['ACCEPT_VERIFIED_MATCH','NORMALIZE_COMPARISON','REQUEST_ADDITIONAL_EVIDENCE','INVESTIGATE_POSITION_SHORTAGE','OPEN_COST_BASIS_CASE','ESCALATE_UNSUPPORTED_CHANGE'];
const errors = [];
const report = (valid) => ({
  ...n, workflowOutcome: valid && !c.missingEvidence.length && !a.findings.some(f => f.evidenceStatus === 'CONFLICTING') ? 'INVESTIGATION_COMPLETED' : 'INVESTIGATION_REVIEW_REQUIRED',
  reconciliationOutcome: n.workflowOutcome, documentEvidenceStatus: c.documentEvidenceStatus,
  investigationStatus: valid ? 'COMPLETED' : 'INVALID_AGENT_OUTPUT',
  investigationSummary: valid ? a.investigationSummary : 'Agent output failed independent validation; human investigation is required.',
  overallRiskLevel: valid ? a.overallRiskLevel : null, findings: valid ? a.findings : [],
  unresolvedQuestions: valid ? a.unresolvedQuestions : [], validationErrors: errors,
  evidenceRecords: c.evidenceRecords, missingEvidence: c.missingEvidence,
  unresolvedExceptions: c.exceptions.filter(e => e.resolutionStatus !== 'EXPLAINED'),
  recommendedNextActions: valid ? [...new Set(a.findings.map(f => f.recommendedAction))] : ['REQUEST_ADDITIONAL_EVIDENCE'],
  humanReviewRequired: true, correctionsApplied: 0, transferCompleted: false
});
if (!keys(a, ['transferId','investigationSummary','overallRiskLevel','findings','unresolvedQuestions','documentEvidenceStatus','requiresHumanReview']) ||
    a.transferId !== c.transferId || !text(a.investigationSummary) || !levels.includes(a.overallRiskLevel) ||
    a.documentEvidenceStatus !== c.documentEvidenceStatus || a.requiresHumanReview !== true ||
    !list(a.unresolvedQuestions) || !a.unresolvedQuestions.every(text) || !list(a.findings) ||
    a.findings.length !== c.exceptions.length || !a.findings.length) {
  errors.push('INVALID_REPORT_CONTRACT'); return report(false);
}
const seen = new Set();
for (const f of a.findings) {
  if (!keys(f,['exceptionId','securityId','classification','rootCause','evidenceIds','confidence','evidenceStatus','recommendedAction','requiresHumanReview'])) {
    errors.push('INVALID_FINDING_CONTRACT'); continue;
  }
  const e = c.exceptions.find(e => e.exceptionId === f.exceptionId);
  if (!e || seen.has(f.exceptionId) || f.securityId !== e.securityId || !c.securityIdentifiers.some(s => s.securityId === f.securityId)) {
    errors.push('INVALID_EXCEPTION_OR_SECURITY'); continue;
  }
  seen.add(f.exceptionId);
  // Classification is the deterministic backend exception type, never AI reclassification.
  if (f.classification !== e.exceptionType || !text(f.rootCause) || !levels.includes(f.confidence) ||
      !['VERIFIED','INCOMPLETE','CONFLICTING'].includes(f.evidenceStatus) || f.requiresHumanReview !== true ||
      !actions.includes(f.recommendedAction) || !list(f.evidenceIds) || !f.evidenceIds.length ||
      new Set(f.evidenceIds).size !== f.evidenceIds.length) {
    errors.push('UNSUPPORTED_FINDING'); continue;
  }
  const records = f.evidenceIds.map(id => c.evidenceRecords.filter(r => r.evidenceId === id && r.securityId === f.securityId));
  if (records.some(matches => !matches.length || matches.some(r => !r.verified))) errors.push('INVALID_EVIDENCE_REFERENCE');
  const explained = e.resolutionStatus === 'EXPLAINED';
  const basis = e.exceptionType.startsWith('COST_BASIS_');
  const supportedReference = records.some(matches => matches.some(r =>
    ['CORPORATE_ACTION','IDENTIFIER_MAPPING'].includes(r.kind) && r.verified && e.evidenceReferences.includes(r.evidenceId)));
  if (['ACCEPT_VERIFIED_MATCH','NORMALIZE_COMPARISON'].includes(f.recommendedAction) &&
      (!explained || !supportedReference || f.evidenceStatus !== 'VERIFIED')) errors.push('UNSUPPORTED_CORRECTIVE_RECOMMENDATION');
  if (!explained && f.evidenceStatus === 'VERIFIED') errors.push('UNRESOLVED_CAUSE_CANNOT_BE_VERIFIED');
  if (f.evidenceStatus === 'VERIFIED' && explained && !supportedReference) errors.push('MISSING_INDEPENDENT_REFERENCE');
  if (f.evidenceStatus === 'CONFLICTING' && !['REQUEST_ADDITIONAL_EVIDENCE','ESCALATE_UNSUPPORTED_CHANGE'].includes(f.recommendedAction)) errors.push('CONFLICT_REQUIRES_REVIEW');
  if (f.recommendedAction === 'OPEN_COST_BASIS_CASE' && !basis) errors.push('INVALID_COST_BASIS_RECOMMENDATION');
  if (basis && !['OPEN_COST_BASIS_CASE','REQUEST_ADDITIONAL_EVIDENCE','ESCALATE_UNSUPPORTED_CHANGE'].includes(f.recommendedAction)) errors.push('COST_BASIS_REQUIRES_SEPARATE_CASE');
  if (f.recommendedAction === 'INVESTIGATE_POSITION_SHORTAGE' && (explained || basis || typeof e.difference !== 'string' || !e.difference.startsWith('-'))) errors.push('NO_BACKEND_SHORTAGE');
}
return report(errors.length === 0);
