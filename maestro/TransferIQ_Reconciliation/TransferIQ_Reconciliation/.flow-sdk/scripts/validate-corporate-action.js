// Current in-Flow Extract docs expose output.result. Scalar taxonomy projection
// is intentionally strict and MUST be confirmed against a real node trace.
// Unknown wrappers, arrays, duplicate values and guessed aliases never verify.
const reconciliation = $vars.NormalizeReconciliation.output;
const discrepancies = [];
const fields = { securityId: null, securityName: null, actionType: null, splitNumerator: null,
  splitDenominator: null, effectiveDate: null, noticeDate: null, evidenceReference: null };
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const text = x => typeof x === 'string' && x.length > 0 && x.length <= 256 && x.trim() === x;
const output = Reflect.get($vars, 'CorporateActionExtractor')?.output;
const finish = extractionStatus => ({
  ...reconciliation,
  evidenceOutcome: extractionStatus === 'VERIFIED' ? 'EVIDENCE_VERIFIED' : 'EVIDENCE_REVIEW_REQUIRED',
  extractionResult: {
    transferId: reconciliation.transferId, documentType: 'CORPORATE_ACTION_NOTICE',
    extractedFields: fields, evidenceReference: fields.evidenceReference ?? null,
    validationStatus: extractionStatus === 'VERIFIED' ? 'VERIFIED' : 'REVIEW_REQUIRED',
    discrepancies, extractionStatus,
  },
});
const owns = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
if (!object(output) || !owns(output, 'version') || !owns(output, 'type') ||
    !owns(output, 'taxonomy') || !owns(output, 'metadata') || !object(output.result) || output.error) {
  discrepancies.push('UNSUPPORTED_OR_FAILED_IXP_OUTPUT');
  return finish('EXTRACTION_FAILED');
}
const names = ['securityId', 'securityName', 'actionType', 'splitNumerator', 'splitDenominator', 'effectiveDate', 'noticeDate', 'evidenceReference'];
for (const name of names) {
  const value = output.result[name];
  if (typeof value === 'string' && value.length <= 256 || typeof value === 'number' && Number.isFinite(value)) fields[name] = value;
  else discrepancies.push('MISSING_OR_INVALID_' + name);
}
for (const name of ['securityId', 'securityName', 'actionType', 'evidenceReference']) {
  if (!text(fields[name])) discrepancies.push('INVALID_' + name);
}
for (const name of ['splitNumerator', 'splitDenominator']) {
  // Integer ratios only, matching the backend reference contract. No quantity
  // arithmetic or binary floating-point financial calculation is performed.
  if (!Number.isSafeInteger(fields[name]) || fields[name] <= 0 || fields[name] > 1000000000) discrepancies.push('INVALID_' + name);
}
const date = x => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(x) &&
  !Number.isNaN(Date.parse(x + 'T00:00:00Z')) && new Date(x + 'T00:00:00Z').toISOString().slice(0, 10) === x;
for (const name of ['effectiveDate', 'noticeDate']) if (!date(fields[name])) discrepancies.push('INVALID_' + name);
const relevant = reconciliation.exceptions.filter(e => e.exceptionType === 'CORPORATE_ACTION_TIMING' && e.securityId === fields.securityId &&
  e.evidenceReferences.includes(fields.evidenceReference));
if (!relevant.length) discrepancies.push('NO_MATCHING_TRANSFER_EXCEPTION_EVIDENCE');
const response = Reflect.get($vars, 'GetCorporateActionReference')?.output;
const body = response?.body;
if ((response && (Reflect.get(response, 'code') ?? Reflect.get(response, 'statusCode'))) !== 200 || !object(body) ||
    body.runId !== Reflect.get(reconciliation, 'demoRunId') || body.transferId !== reconciliation.transferId ||
    body.fictionalDemo !== true || body.referenceSource !== 'SEEDED_REFERENCE_DATABASE' ||
    !Array.isArray(body.items) || !Number.isSafeInteger(body.total) || body.total !== body.items.length ||
    body.offset !== 0 || !Number.isSafeInteger(body.limit) || body.limit < body.total) {
  discrepancies.push('REFERENCE_UNAVAILABLE_OR_INVALID');
  return finish('REVIEW_REQUIRED');
}
const matches = body.items.filter(r => object(r) && r.securityId === fields.securityId && r.evidenceReference === fields.evidenceReference);
if (matches.length !== 1) discrepancies.push('REFERENCE_NOT_UNIQUE_OR_NOT_FOUND');
else {
  const r = matches[0];
  if (r.verified !== true) discrepancies.push('REFERENCE_NOT_VERIFIED');
  if (r.noticeDateSource !== 'REFERENCE_CREATED_AT') discrepancies.push('UNKNOWN_NOTICE_DATE_PROVENANCE');
  const action = x => x === 'SPLIT' ? 'STOCK_SPLIT' : x;
  // This phase supports split notices only; other actions require investigation.
  if (action(fields.actionType) !== 'STOCK_SPLIT' || action(r.actionType) !== 'STOCK_SPLIT') discrepancies.push('ACTION_TYPE_MISMATCH_OR_UNSUPPORTED');
  for (const [key, reference] of [['securityName', 'securityName'], ['splitNumerator', 'numerator'],
    ['splitDenominator', 'denominator'], ['effectiveDate', 'effectiveDate'], ['noticeDate', 'noticeDate']]) {
    if (fields[key] !== r[reference]) discrepancies.push('REFERENCE_MISMATCH_' + key);
  }
}
// A verified notice never clears the remaining exception or authorizes changes.
return finish(discrepancies.length ? 'REVIEW_REQUIRED' : 'VERIFIED');
