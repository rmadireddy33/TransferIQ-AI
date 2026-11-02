const response = $vars.GetTransferDetails.output;
// Designer schema uses code; SDK 6.66.5 documents statusCode. Validate either envelope.
const httpStatus = response && (Reflect.get(response, 'code') ?? Reflect.get(response, 'statusCode'));
const body = response && response.body;
if (!response || httpStatus !== 200 || !body || typeof body !== 'object' || Array.isArray(body) ||
    body.transferId !== $vars.ValidateInput.output.transferId ||
    !['transferId', 'clientId', 'deliveringFirmId', 'receivingFirmId', 'sourceAccountId', 'destinationAccountId'].every(k => typeof body[k] === 'string' && body[k].length > 0) ||
    !['DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'EXCEPTION_DETECTED', 'INVESTIGATING', 'PENDING_APPROVAL', 'RESOLVED', 'ESCALATED', 'COMPLETED'].includes(body.status) ||
    !['FULL', 'PARTIAL'].includes(body.transferType)) throw new Error('INVALID_RESPONSE');
// Preserve the API shape: the lifecycle field is status, not transferStatus.
return body;
