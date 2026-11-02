const response = $vars.GetDeliveringPositions.output;
const httpStatus = response && (Reflect.get(response, 'code') ?? Reflect.get(response, 'statusCode'));
const page = response && response.body;
if (!response || httpStatus !== 200 || !page || !Array.isArray(page.items) ||
    !Number.isSafeInteger(page.total) || page.total < 1 || page.total !== page.items.length || page.offset !== 0 || page.limit !== 100 ||
    !page.items.every(p => p && typeof p.positionId === 'string' && typeof p.securityId === 'string' &&
      p.accountId === $vars.ValidateTransfer.output.sourceAccountId && typeof p.quantity === 'string' &&
      /^\d+(\.\d+)?$/.test(p.quantity) && typeof p.snapshotDate === 'string')) throw new Error('INVALID_RESPONSE');
// Never silently accept a truncated page. Step 5 supports <=100 rows per side.
return page;
