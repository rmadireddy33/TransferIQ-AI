// Reached only through the corresponding real Quick Form outcome port.
const form = $vars.quickForm1.output;
const outcome = '__OUTCOME__';
const label = {APPROVE:'Approve',REQUEST_EVIDENCE:'Request Evidence',ESCALATE:'Escalate',REJECT:'Reject'}[outcome];
if (!form || typeof form !== 'object' || form.Action !== label) throw new Error('MISSING_OR_MISMATCHED_HUMAN_FORM_OUTPUT');
const value = key => {
  // Use the saved Studio field ID; older task field names remain validated aliases.
  const result = key === 'reviewerComments' ? (Reflect.get(form, 'reviewerCommentsOptional') ?? Reflect.get(form, 'Reviewer comments (optional)') ?? Reflect.get(form, 'comments') ?? Reflect.get(form, 'reviewerComments') ?? '') : (Reflect.get(form, key) ?? '');
  if (typeof result !== 'string' || result.length > 2000) throw new Error('INVALID_REVIEW_TEXT');
  return result;
};
const plan = $vars.ValidateResolutionPlan.output;
return {planVersion:plan.planVersion,planHash:plan.planHash,reviewOutcome:outcome,
  reviewerReference:$vars.ValidateInput.output.reviewerReference,
  reviewerComments:value('reviewerComments'),additionalInformation:value('additionalInformation'),
  // Correlation reference, NOT a claimed verified Action Center task ID.
  reviewEventReference:$vars.ValidateInput.output.correlationId + ':TransferOperationsReview'};
