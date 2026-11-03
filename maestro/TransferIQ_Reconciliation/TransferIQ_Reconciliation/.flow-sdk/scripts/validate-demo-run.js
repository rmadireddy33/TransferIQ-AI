const response = $vars.CreateDemoRun.output;
const body = response?.body;
if (![200, 201].includes(response?.code ?? (response && Reflect.get(response, 'statusCode'))) || !body ||
    !/^DEMO-[0-9a-f]{32}$/.test(body.runId) ||
    body.transferId !== $vars.ValidateInput.output.transferId ||
    body.fictionalDemo !== true || body.evidenceMode !== 'LIVE_SYNTHETIC_BACKEND' ||
    typeof body.expiresAt !== 'number' || !Number.isFinite(body.expiresAt) || body.expiresAt <= 0) {
  throw new Error('INVALID_DEMO_RUN');
}
return { runId: body.runId, transferId: body.transferId };
