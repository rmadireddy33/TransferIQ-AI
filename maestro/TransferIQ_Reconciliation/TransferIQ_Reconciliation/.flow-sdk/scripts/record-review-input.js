// Reached only through the corresponding real Quick Form outcome port.
const form = $vars.TransferOperationsReview.output;
const outcome = '__OUTCOME__';
const label = {APPROVE:'Approve Disposition',REQUEST_EVIDENCE:'Request Evidence',ESCALATE:'Escalate',REJECT:'Reject'}[outcome];
if (!form || typeof form !== 'object' || form.Action !== label) throw new Error('MISSING_OR_MISMATCHED_HUMAN_FORM_OUTPUT');
const value = key => {
  const result = form[key] ?? '';
  if (typeof result !== 'string' || result.length > 2000) throw new Error('INVALID_REVIEW_TEXT');
  return result;
};
const plan = $vars.ValidateResolutionPlan.output;
return {planVersion:plan.planVersion,planHash:plan.planHash,reviewOutcome:outcome,
  reviewerReference:$vars.StartTransferInvestigation.output.reviewerReference,
  reviewerComments:value('reviewerComments'),additionalInformation:value('additionalInformation'),
  // Correlation reference, NOT a claimed verified Action Center task ID.
  reviewEventReference:$vars.ValidateInput.output.correlationId + ':TransferOperationsReview'};
