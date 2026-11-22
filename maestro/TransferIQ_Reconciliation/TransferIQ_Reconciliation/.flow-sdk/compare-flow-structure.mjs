import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const [canonicalArg, candidateArg] = process.argv.slice(2);
if (!canonicalArg || !candidateArg) {
  throw new Error('Usage: node compare-flow-structure.mjs <canonical.flow> <candidate.flow>');
}

const readFlow = path => JSON.parse(readFileSync(resolve(path), 'utf8'));
const canonical = readFlow(canonicalArg);
const candidate = readFlow(candidateArg);
const ids = flow => new Set(flow.nodes.map(node => node.id));
const edgeKey = edge => [edge.sourceNodeId, edge.sourcePort, edge.targetNodeId, edge.targetPort].join('|');
const edges = flow => new Set(flow.edges.map(edgeKey));
const difference = (left, right) => [...left].filter(value => !right.has(value)).sort();
const canonicalIds = ids(canonical);
const candidateIds = ids(candidate);
const canonicalEdges = edges(canonical);
const candidateEdges = edges(candidate);

const criticalTypes = [
  ['StartTransferInvestigation', 'core.trigger.manual'],
  ['PortalWebhook', 'uipath.connector.trigger.uipath-http-webhook.http-webhook'],
  ['TransferInvestigationAgent', 'uipath.agent.autonomous'],
  ['quickForm1', 'uipath.human-in-the-loop.quick-form'],
  ['ApproveDisposition', 'core.action.script'],
  ['RejectDisposition', 'core.action.script'],
  ['RecordReviewDecision', 'core.action.http.v2'],
];

const node = (flow, id) => flow.nodes.find(item => item.id === id);
const quickFormShape = flow => {
  const form = node(flow, 'quickForm1');
  return {
    type: form?.type,
    version: form?.typeVersion,
    fields: form?.inputs?.schema?.fields?.map(({ id, type, direction, label }) => ({ id, type, direction, label })),
    outcomes: form?.inputs?.schema?.outcomes?.map(({ id, name, action, isPrimary }) => ({ id, name, action, isPrimary })),
    recipient: form?.inputs?.recipient,
  };
};
const agentInputs = flow => node(flow, 'TransferInvestigationAgent')?.inputs?.agentInputVariables;

const report = {
  canonical: { nodes: canonical.nodes.length, edges: canonical.edges.length },
  candidate: { nodes: candidate.nodes.length, edges: candidate.edges.length },
  missingNodeIds: difference(canonicalIds, candidateIds),
  extraNodeIds: difference(candidateIds, canonicalIds),
  missingEdges: difference(canonicalEdges, candidateEdges),
  extraEdges: difference(candidateEdges, canonicalEdges),
  criticalTypeMismatches: criticalTypes.flatMap(([id, expected]) => {
    const actual = node(candidate, id)?.type;
    return actual === expected ? [] : [{ id, expected, actual }];
  }),
  quickFormEquivalent: JSON.stringify(quickFormShape(canonical)) === JSON.stringify(quickFormShape(candidate)),
  agentInputsEquivalent: JSON.stringify(agentInputs(canonical)) === JSON.stringify(agentInputs(candidate)),
};

const valid = report.canonical.nodes === report.candidate.nodes &&
  report.canonical.edges === report.candidate.edges &&
  !report.missingNodeIds.length && !report.extraNodeIds.length &&
  !report.missingEdges.length && !report.extraEdges.length &&
  !report.criticalTypeMismatches.length && report.quickFormEquivalent && report.agentInputsEquivalent;

console.log(JSON.stringify({ valid, ...report }, null, 2));
if (!valid) process.exitCode = 1;
