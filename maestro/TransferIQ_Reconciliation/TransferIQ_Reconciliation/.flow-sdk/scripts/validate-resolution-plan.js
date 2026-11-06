const response = $vars.PreviewResolutionPlan.output;
const p = response?.body;
const expected = $vars.BuildResolutionPlan.output;
const canonical = x => Array.isArray(x) ? x.map(canonical) : x && typeof x === 'object' ?
  Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])) : x;
const same = (a,b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
if (!response || (Reflect.get(response,'code') ?? Reflect.get(response,'statusCode')) !== 200 || !p || p.contractVersion !== '1.0' ||
    p.demoOnly !== true || p.identityVerification !== 'UNVERIFIED_DEMO_REFERENCE' || p.status !== 'PREVIEWED' ||
    !/^PLAN-[0-9a-f-]{36}$/.test(p.planId) || p.planVersion !== 1 || !/^[0-9a-f]{64}$/.test(p.planHash) ||
    p.transferId !== expected.transferId || p.reconciliationRunId !== expected.reconciliationRunId ||
    p.investigationSummary !== expected.investigationSummary || p.overallRiskLevel !== expected.overallRiskLevel ||
    p.documentEvidenceStatus !== expected.documentEvidenceStatus || !same(p.proposedActions,expected.proposedActions) ||
    typeof p.expiresAt !== 'number' || p.expiresAt * 1000 <= Date.now() ||
    !same(p.evidenceReferences,[...new Set(expected.proposedActions.flatMap(a=>a.evidenceReferences))].sort())) {
  throw new Error('INVALID_RESOLUTION_PLAN');
}
const exceptions = $vars.NormalizeReconciliation.output.exceptions;
const describe = security => {
  const e = exceptions.find(e => e.securityId === security);
  return e ? JSON.stringify({securityId:e.securityId,status:e.resolutionStatus,description:e.description,
    sourceQuantity:e.sourceQuantity,targetQuantity:e.targetQuantity,expectedQuantity:e.expectedQuantity,
    difference:e.difference,evidenceReferences:e.evidenceReferences}) : 'Not applicable to this transfer';
};
return {...p,exceptionCount:String(exceptions.length),corporateActionExplanation:describe('SEC-103'),
  shortageExplanation:describe('SEC-104'),evidenceDisplay:JSON.stringify(p.evidenceReferences),
  dispositionDisplay:JSON.stringify(p.proposedActions),
  demoNotice:'Fictional, isolated review. No custody or staging changes. Review identity is an unverified demo reference. Shortages remain unresolved.'};
