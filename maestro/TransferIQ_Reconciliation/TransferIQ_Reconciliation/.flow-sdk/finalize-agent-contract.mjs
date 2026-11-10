// SDK returns supports primitive types only. Apply the authored required schema
// after compilation/merge, before product validation or packaging. No runtime
// output is supplied or repaired here; independent validation stays fail-closed.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const sourceDir = dirname(fileURLToPath(import.meta.url));
const flowPath = resolve(process.argv[2] || join(sourceDir, '../TransferIQ_Reconciliation.flow'));
const flow = JSON.parse(readFileSync(flowPath, 'utf8'));
const node = flow.nodes.find(n => n.id === 'TransferInvestigationAgent');
const agentSource = node?.inputs?.source ?? node?.source ?? node?.model?.source;
if (node?.type !== 'uipath.agent.autonomous' || typeof agentSource !== 'string' ||
    !/^[0-9a-f-]{36}$/i.test(agentSource)) throw new Error('INVALID_INLINE_AGENT_IDENTITY');
const agentPath = join(dirname(flowPath), agentSource, 'agent.json');
const preservedAgentPath = join(sourceDir, '..', agentSource, 'agent.json');
const agent = JSON.parse(readFileSync(existsSync(agentPath) ? agentPath : preservedAgentPath, 'utf8'));
const schema = JSON.parse(readFileSync(join(sourceDir, 'agent-output-schema.json'), 'utf8'));
const types = s => Object.entries(s.properties || {}).map(([k, v]) => [k, v.type]).sort();
if (JSON.stringify(types(agent.outputSchema)) !== JSON.stringify(types(schema))) {
  throw new Error('AGENT_OUTPUT_SCHEMA_DRIFT: reconcile returns and authored schema before building');
}
agent.outputSchema = schema;
const systemMessage = agent.messages.find(m => m.role === 'system');
if (!systemMessage) throw new Error('MISSING_AGENT_SYSTEM_MESSAGE');
systemMessage.content = readFileSync(join(sourceDir, 'agent-system-prompt.txt'), 'utf8');
systemMessage.contentTokens = [{type:'simpleText',rawString:systemMessage.content}];
mkdirSync(dirname(agentPath), {recursive:true});
writeFileSync(agentPath, JSON.stringify(agent, null, 2) + '\n');
console.log('Applied required TransferIQ agent output contract; no runtime defaults.');
