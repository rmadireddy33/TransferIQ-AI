const body = name => {
  const response = Reflect.get($vars,name)?.output;
  if ((response?.code ?? response?.statusCode) !== 200 || !response.body) throw new Error('REVIEW_READ_FAILED');
  return response.body;
};
const p = body('ReadResolutionPlan'), r = body('ReadLatestReconciliation');
const report = body('VerifyDemoDisposition'), audit = body('ReadReviewAudit');
const before = $vars.ValidateResolutionPlan.output, decision = $vars.reviewDecision;
const original = $vars.RunReconciliation.output.body;
const canonical = x => Array.isArray(x) ? x.map(canonical) : x && typeof x === 'object' ?
  Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])) : x;
const same = (a,b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
const sorted = xs => [...xs].sort((a,b)=>a.exceptionId.localeCompare(b.exceptionId));
const outcomes = {APPROVE:'REVIEWED_WITH_OPEN_EXCEPTIONS',REQUEST_EVIDENCE:'EVIDENCE_REQUESTED',ESCALATE:'ESCALATED',REJECT:'REVIEW_REJECTED'};
const statuses = {ACCEPT_VERIFIED_EXPLANATION:'ACKNOWLEDGED',REQUEST_ADDITIONAL_EVIDENCE:'EVIDENCE_REQUESTED',ESCALATE_TO_TRANSFER_OPERATIONS:'OPEN_ESCALATED',OPEN_COST_BASIS_CASE:'OPEN_BASIS_CASE'};
const expected = decision.reviewOutcome === 'REJECT' ? [] : before.proposedActions.map(a => {
  const action = {REQUEST_EVIDENCE:'REQUEST_ADDITIONAL_EVIDENCE',ESCALATE:'ESCALATE_TO_TRANSFER_OPERATIONS'}[decision.reviewOutcome] || a.disposition;
  return {exceptionId:a.exceptionId,disposition:action,status:statuses[action]};
});
const finalStatus = decision.reviewOutcome === 'REJECT' ? 'REJECTED' : 'EXECUTED';
if (p.planId !== before.planId || p.planHash !== before.planHash || p.planVersion !== before.planVersion || p.status !== finalStatus ||
    !p.decision || !Object.keys(decision).filter(k=>!['planVersion','planHash'].includes(k)).every(k=>p.decision[k] === decision[k]) ||
    r.transferId !== original.transferId || r.reconciliationRunId !== original.reconciliationRunId || r.inputFingerprint !== original.inputFingerprint ||
    !same(sorted(r.exceptions),sorted(original.exceptions)) ||
    report.planId !== before.planId || report.planStatus !== finalStatus || report.transferId !== before.transferId ||
    report.reconciliationRunId !== before.reconciliationRunId || report.humanReviewOutcome !== decision.reviewOutcome ||
    report.workflowOutcome !== outcomes[decision.reviewOutcome] || report.verificationStatus !== 'VERIFIED_DEMO_STATE' ||
    report.positionsUnchanged !== true || report.transferCompleted !== false || report.demoOnly !== true ||
    report.identityVerification !== 'UNVERIFIED_DEMO_REFERENCE' || !same(sorted(report.reviewedDispositions),sorted(expected)) ||
    !same(sorted(report.unresolvedExceptions),sorted(r.exceptions.filter(e=>e.resolutionStatus !== 'EXPLAINED'))) ||
    audit.planId !== before.planId || !Array.isArray(audit.items) || audit.items.length !== 3 ||
    !audit.items.every(e=>e.planId === before.planId && e.transferId === before.transferId && report.auditEventIds.includes(e.auditEventId)) ||
    !['PLAN_PREVIEWED','DEMO_REVIEW_RECORDED',decision.reviewOutcome === 'REJECT' ? 'DEMO_DISPOSITION_REJECTED' : 'DEMO_DISPOSITION_EXECUTED'].every(t=>audit.items.some(e=>e.eventType === t))) {
  throw new Error('INDEPENDENT_REVIEW_VERIFICATION_FAILED');
}
return {...report,auditReference:'/api/demo/runs/' + encodeURIComponent($vars.ValidateDemoRun.output.runId) + '/resolution-plans/' + encodeURIComponent(p.planId) + '/audit',
  correctionsApplied:0, reviewEventReference:decision.reviewEventReference};
