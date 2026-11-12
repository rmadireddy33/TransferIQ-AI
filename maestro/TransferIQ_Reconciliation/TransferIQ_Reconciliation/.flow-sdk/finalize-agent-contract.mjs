// SDK returns supports primitive types only. Apply the authored required schema
// after compilation/merge, before product validation or packaging. No runtime
// output is supplied or repaired here; independent validation stays fail-closed.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const sourceDir = dirname(fileURLToPath(import.meta.url));
const flowPath = resolve(process.argv[2] || join(sourceDir, '../TransferIQ_Reconciliation.flow'));
const referenceFlowPath = process.argv[3] ? resolve(process.argv[3]) : null;
const flow = JSON.parse(readFileSync(flowPath, 'utf8'));
const node = flow.nodes.find(n => n.id === 'TransferInvestigationAgent');
const agentSource = node?.inputs?.source ?? node?.source ?? node?.model?.source;
if (node?.type !== 'uipath.agent.autonomous' || typeof agentSource !== 'string' ||
    !/^[0-9a-f-]{36}$/i.test(agentSource)) throw new Error('INVALID_INLINE_AGENT_IDENTITY');
const agentPath = join(dirname(flowPath), agentSource, 'agent.json');
const preservedAgentPath = join(sourceDir, '..', agentSource, 'agent.json');
const referenceFlow = referenceFlowPath ? JSON.parse(readFileSync(referenceFlowPath, 'utf8')) : null;
const referenceNode = referenceFlow?.nodes?.find(n => n.id === 'TransferInvestigationAgent');
const referenceAgentPath = referenceFlowPath ? join(dirname(referenceFlowPath), agentSource, 'agent.json') : null;
const agentSourcePath = referenceAgentPath && existsSync(referenceAgentPath) ? referenceAgentPath :
  (existsSync(agentPath) ? agentPath : preservedAgentPath);
const agent = JSON.parse(readFileSync(agentSourcePath, 'utf8'));
const schema = JSON.parse(readFileSync(join(sourceDir, 'agent-output-schema.json'), 'utf8'));
const types = s => Object.entries(s.properties || {}).map(([k, v]) => [k, v.type]).sort();
if (JSON.stringify(types(agent.outputSchema)) !== JSON.stringify(types(schema))) {
  throw new Error('AGENT_OUTPUT_SCHEMA_DRIFT: reconcile returns and authored schema before building');
}
agent.outputSchema = schema;
const attachmentInput = 'ValidateInput__output__corporateActionPdf';
if (!agent.inputSchema?.properties?.[attachmentInput]) throw new Error('MISSING_AGENT_ATTACHMENT_INPUT');
agent.inputSchema.properties[attachmentInput] = { $ref: '#/definitions/job-attachment' };
agent.inputSchema.definitions = {
  ...(agent.inputSchema.definitions || {}),
  'job-attachment': {
    type: 'object',
    properties: {
      ID: { type: 'string' }, FullName: { type: 'string' }, MimeType: { type: 'string' },
      Metadata: { type: 'object', additionalProperties: { type: 'string' } }
    },
    required: ['ID'],
    'x-uipath-resource-kind': 'JobAttachment'
  }
};
const attachmentBinding = node.inputs?.agentInputVariables?.find(x => x.id === attachmentInput);
if (!attachmentBinding) throw new Error('MISSING_FLOW_ATTACHMENT_BINDING');
attachmentBinding.type = 'object';
const systemMessage = agent.messages.find(m => m.role === 'system');
if (!systemMessage) throw new Error('MISSING_AGENT_SYSTEM_MESSAGE');
if (typeof systemMessage.content !== 'string' || !systemMessage.content.trim()) {
  systemMessage.content = readFileSync(join(sourceDir, 'agent-system-prompt.txt'), 'utf8');
}
systemMessage.contentTokens = [{type:'simpleText',rawString:systemMessage.content}];
const userMessage = agent.messages.find(m => m.role === 'user');
if (!userMessage) throw new Error('MISSING_AGENT_USER_MESSAGE');
if (referenceFlow) {
  node.inputs.systemPrompt = systemMessage.content;
  node.inputs.userPrompt = userMessage.content;
}
mkdirSync(dirname(agentPath), {recursive:true});
writeFileSync(agentPath, JSON.stringify(agent, null, 2) + '\n');
writeFileSync(flowPath, JSON.stringify(flow, null, 2) + '\n');
console.log('Applied required TransferIQ agent output contract; no runtime defaults.');
