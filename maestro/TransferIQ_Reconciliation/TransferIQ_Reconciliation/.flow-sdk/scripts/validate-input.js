const transferId = $vars.StartTransferInvestigation.output.transferId;
if (typeof transferId !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(transferId)) throw new Error('INVALID_TRANSFER_INPUT');
return { transferId, correlationId: 'TIQ-' + Date.now() + '-' + Math.random().toString(36).slice(2, 12) };
