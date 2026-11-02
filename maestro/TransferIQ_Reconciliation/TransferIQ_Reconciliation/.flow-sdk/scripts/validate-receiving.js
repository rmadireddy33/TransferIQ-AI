const response = $vars.GetReceivingPositions.output;
const httpStatus = response && (Reflect.get(response, 'code') ?? Reflect.get(response, 'statusCode'));
const page = response && response.body;
if (!response || httpStatus !== 200 || !page || !Array.isArray(page.items) ||
    !Number.isSafeInteger(page.total) || page.total < 0 || page.total !== page.items.length || page.offset !== 0 || page.limit !== 100 ||
    page.positionKind !== 'RECEIVING_TRANSFER_STAGING' || page.settledHoldings !== false ||
    !page.items.every(p => p && typeof p.stagingPositionId === 'string' && typeof p.securityId === 'string' &&
      p.transferId === $vars.ValidateInput.output.transferId && typeof p.quantity === 'string' && /^\d+(\.\d+)?$/.test(p.quantity) &&
      Number.isSafeInteger(p.version) && p.version >= 1 && typeof p.status === 'string')) throw new Error('INVALID_RESPONSE');
// Empty staging is evidence: the backend must classify missing securities.
return page;
