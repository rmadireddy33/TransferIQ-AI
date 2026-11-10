import { readFileSync } from 'node:fs';
import { flow, manual, script, rawNode, types, out } from '@uipath/maestro-builder-sdk';
const read = (name: string) => JSON.parse(readFileSync(new URL(name, import.meta.url), 'utf8').replace(/^\uFEFF/, ''));
const { quickFormReviewerEmail: reviewer } = read('runtime.local.json');
if (typeof reviewer !== 'string' || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(reviewer)) throw new Error('Configure the verified reviewer in runtime.local.json');
const manifest = read('quick-form.v1.9.manifest.json');
export default flow('2500f5ae-1629-46c6-ad2e-6b0314bf9827')
.schemaVersion('1.9').name('QuickFormSmokeTest')
.trigger(manual(), {version:'1.0'})
.output({result:types.object})
.step('DummyData',script({code:"return {summary:'TEST ONLY: fictional transfer TEST-001. Approve or reject this Quick Form connectivity test. No financial action will occur.'};",returns:{summary:'string'}}))
.step('QuickFormReview',rawNode({
 nodeType:'uipath.human-in-the-loop.quick-form',version:'1.9',manifest,
 inputs:{schema:{schemaId:'14c7e6d0-bc3d-4c58-a452-eab093078684',title:'TransferIQ Quick Form Smoke Test',
 fields:[{id:'summary',label:'Dummy test summary',type:'string',direction:'input',binding:'vars.DummyData.output.summary'},{id:'comments',label:'Comments (optional)',type:'string',direction:'output'}],
 outcomes:[{id:'approve',name:'Approve',type:'string',isPrimary:true,action:'Continue'},{id:'reject',name:'Reject',type:'string',isPrimary:false,action:'Continue'}]},
 enableDecisionSchema:false,
 recipient:{channels:['ActionCenter'],connections:{},assignee:{type:'user',value:reviewer,displayName:reviewer}}},
 outputs:{output:{...manifest.outputDefinition.output,properties:{comments:{type:'string',fieldId:'comments'},Action:{type:'string',enum:['Approve','Reject'],default:'Approve'}}},status:{...manifest.outputDefinition.status,enum:['Approve','Reject'],default:'Approve'}}
}))
.stepToList('outcome-reject',b=>b.stepToRef('CaptureDecision'))
.stepToList('outcome-approve',b=>b
 .step('CaptureDecision',script({code:"const result=$vars.QuickFormReview.output; if (!result || !['Approve','Reject'].includes(result.Action)) throw new Error('Missing actual human outcome'); if (result.comments != null && typeof result.comments !== 'string') throw new Error('Invalid comments'); return {testOnly:true,outcome:result.Action,comments:result.comments || '',summary:$vars.DummyData.output.summary};",returns:{testOnly:'boolean',outcome:'string',comments:'string',summary:'string'}}))
 .return({result:out('CaptureDecision')},{name:'TestResult'}))
.openTails().build();
