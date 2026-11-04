/** Local contract/graph harness, NOT a UiPath runtime or an Integration Service emulator.
 * Executes the emitted scripts/decisions/edges. HTTP responses come from a real
 * backend or explicitly supplied isolated test fixtures. Never used by the Flow.
 */
import fs from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const artifact = new URL('../maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/TransferIQ_Reconciliation.flow', import.meta.url);
export const flow = JSON.parse(fs.readFileSync(artifact, 'utf8'));
const expression = (code, vars) => vm.runInNewContext(code, { $vars: vars }, { timeout: 1000 });
const dynamic = (x, vars) => typeof x === 'string' && x.startsWith('=js:') ? expression(x.slice(4), vars) : x;

export async function runLocal({ transferId, corporateActionPdf = null, responses, localTransport = false, baseUrl, fault, errorEnvelope = 'output' }) {
  const vars = Object.fromEntries(flow.variables.globals.map(v => [v.id, v.defaultValue]));
  vars.StartTransferInvestigation = { output: { transferId, corporateActionPdf } };
  const calls = [], trace = [];
  let id = 'StartTransferInvestigation';
  for (let budget = 0; budget < 100; budget++) {
    const node = flow.nodes.find(n => n.id === id);
    if (!node) throw new Error('Unknown graph node');
    trace.push(id);
    let port;
    try {
      if (node.type === 'core.trigger.manual') port = 'output';
      else if (node.type === 'core.action.script') {
        const value = expression('(function(){' + node.inputs.script + '\n})()', vars);
        vars[id] = { output: value }; port = 'success';
      } else if (node.type === 'core.logic.decision') port = expression(node.inputs.expression, vars) ? 'true' : 'false';
      else if (node.type === 'core.control.end') {
        return { result: expression(node.outputs.result.source.expression, vars), trace, calls, evidenceMode: 'LOCAL_CONTRACT_HARNESS_NOT_UIPATH_RUNTIME' };
      } else if (node.type === 'core.action.http.v2') {
        if (!localTransport) throw new Error('Local HTTP requires explicit adapter');
        const params = node.inputs.detail.bodyParameters;
        let response;
        for (let attempt = 0; attempt <= node.inputs.retryCount; attempt++) {
          const url = new URL(dynamic(params.url, vars), vars.backendBaseUrl);
          if (baseUrl) {
            const target = new URL(baseUrl);
            url.protocol = target.protocol; url.host = target.host;
          }
          for (const [key, value] of Object.entries(params.query || {})) url.searchParams.set(key, dynamic(value, vars));
          calls.push({ nodeId: id, method: params.method, path: url.pathname + url.search, attempt: attempt + 1 });
          try {
            if (fault?.nodeId === id) throw Object.assign(new Error('Injected transport failure'), { status: fault.status || 0 });
            if (responses) {
              if (!(id in responses)) throw new Error('Missing test response');
              response = responses[id];
            } else {
              if (!baseUrl) throw new Error('Missing local backend URL');
              const headers = Object.fromEntries(Object.entries(params.headers || {}).map(([k, v]) => [k, dynamic(v, vars)]));
              const r = await fetch(url, { method: params.method, headers, body: params.method === 'POST' ? dynamic(params.body, vars) : undefined, signal: AbortSignal.timeout(30000), redirect: 'error' });
              response = { code: r.status, body: await r.json() };
            }
            const status = response?.code ?? response?.statusCode;
            calls[calls.length - 1].status = status || null;
            if (!Number.isInteger(status) || status < 200 || status >= 300) throw Object.assign(new Error('HTTP failed'), { status: status || 0 });
            break;
          } catch (e) {
            const status = e.status || 0;
            if (attempt === node.inputs.retryCount || (status !== 0 && status !== 429 && status < 500)) throw e;
          }
        }
        vars[id] = { output: response }; port = 'default';
      } else throw new Error('Unsupported graph node ' + node.type);
    } catch (e) {
      // Explicit test doubles for both managed-HTTP error envelope versions.
      vars[id] = node.type === 'core.action.http.v2'
        ? (errorEnvelope === 'error' ? { error: { status: e.status || null } } : { output: { status: e.status || null }, error: true })
        : { error: { code: 'SCRIPT_FAILURE' } };
      port = 'error';
    }
    const edges = flow.edges.filter(e => e.sourceNodeId === id && e.sourcePort === port);
    if (edges.length !== 1) throw new Error('Expected one edge from ' + id + ':' + port);
    id = edges[0].targetNodeId;
  }
  throw new Error('Graph exceeded bounded step budget');
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const result = await runLocal(input);
  process.stdout.write(JSON.stringify(result));
}
