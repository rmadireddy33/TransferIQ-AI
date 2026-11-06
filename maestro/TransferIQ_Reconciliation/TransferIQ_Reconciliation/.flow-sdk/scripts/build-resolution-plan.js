const report = $vars.ValidateInvestigation.output;
const reconciliation = $vars.NormalizeReconciliation.output;
const reviewer = $vars.StartTransferInvestigation.output.reviewerReference;
if (report.workflowOutcome !== 'INVESTIGATION_COMPLETED' || report.investigationStatus !== 'COMPLETED' ||
    report.documentEvidenceStatus !== 'NOT_PROCESSED_IXP_DISABLED' ||
    typeof reviewer !== 'string' || !reviewer.trim() || reviewer.length > 256 ||
    !/^[A-Za-z0-9_-]{43}$/.test($vars.CreateDemoRun.output.body.reviewCapability)) {
  throw new Error('REVIEW_CONFIGURATION_OR_VALIDATION_REQUIRED');
}
// Agent prose cannot choose an authorized action. Use immutable backend exceptions.
return {
  transferId:reconciliation.transferId, reconciliationRunId:reconciliation.reconciliationRunId,
  agentInvestigationId:$vars.ValidateInput.output.correlationId + ':TransferInvestigationAgent',
  investigationSummary:report.investigationSummary, overallRiskLevel:report.overallRiskLevel,
  documentEvidenceStatus:report.documentEvidenceStatus,
  proposedActions:reconciliation.exceptions.map(e => ({exceptionId:e.exceptionId, securityId:e.securityId,
    evidenceReferences:e.evidenceReferences,
    disposition:e.resolutionStatus === 'EXPLAINED' ? 'ACCEPT_VERIFIED_EXPLANATION' :
      (e.exceptionType.startsWith('COST_BASIS_') ? 'OPEN_COST_BASIS_CASE' : 'ESCALATE_TO_TRANSFER_OPERATIONS')})),
};
