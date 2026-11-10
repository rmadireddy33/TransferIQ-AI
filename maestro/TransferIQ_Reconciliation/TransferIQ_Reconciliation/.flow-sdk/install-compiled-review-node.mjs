// Narrow replacement after brownfield merge: use the SDK-emitted Quick Form in
// full rather than retaining the original node's legacy serialized metadata.
import {readFileSync, writeFileSync} from 'node:fs';
const [compiledPath, targetPath] = process.argv.slice(2);
if (!compiledPath || !targetPath) throw new Error('Usage: compiled.flow merged.flow');
const read = p => JSON.parse(readFileSync(p, 'utf8').replace(/^\uFEFF/, ''));
const compiled = read(compiledPath), target = read(targetPath);
const id = 'TransferOperationsReview';
const node = compiled.nodes.find(n => n.id === id);
const index = target.nodes.findIndex(n => n.id === id);
if (index < 0 || node?.type !== 'uipath.human-in-the-loop.quick-form' ||
    node.model?.serviceType !== 'Actions.HITL' || node.model?.type !== 'bpmn:UserTask') {
  throw new Error('Expected actual SDK Quick Form node');
}
target.nodes[index] = node;
writeFileSync(targetPath, JSON.stringify(target, null, 2) + '\n');
console.log('Replaced only TransferOperationsReview with SDK-emitted node; retained node ID, edges, layout; no legacy designer uniqueId.');
