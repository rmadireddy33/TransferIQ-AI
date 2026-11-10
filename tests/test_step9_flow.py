"""Real isolated backend responses + explicit agent/human TEST DOUBLES, no UiPath runtime."""
import copy
import json
import pytest
from tests.test_maestro_contract import collect, run_graph, FLOW
from tests.test_step8_agent import mock_agent

CORRELATION = 'TEST-STEP9-CORRELATION'
REVIEWER = 'UNVERIFIED_TEST_REVIEWER'
LABELS = {'APPROVE':'Approve','REJECT':'Reject'}
FORM = next(n for n in json.loads(FLOW.read_text())['nodes'] if n['type'] == 'uipath.human-in-the-loop.quick-form')
PORTS = {o['name']: o['id'] for o in FORM['inputs']['schema']['outcomes']}


def review_responses(client, tid, outcome):
    responses = collect(client,tid,review=True)
    run = responses['CreateDemoRun']['body']
    root = '/api/demo/runs/'+run['runId']
    reconciliation = responses['RunReconciliation']['body']
    agent = mock_agent(responses)
    actions = [dict(exceptionId=e['exceptionId'],securityId=e['securityId'],evidenceReferences=e['evidenceReferences'],
        disposition='ACCEPT_VERIFIED_EXPLANATION' if e['resolutionStatus']=='EXPLAINED' else
        ('OPEN_COST_BASIS_CASE' if e['exceptionType'].startswith('COST_BASIS_') else 'ESCALATE_TO_TRANSFER_OPERATIONS'))
        for e in reconciliation['exceptions']]
    headers={'X-Demo-Capability':run['reviewCapability'],'Idempotency-Key':CORRELATION}
    body=dict(transferId=tid,reconciliationRunId=reconciliation['reconciliationRunId'],
        agentInvestigationId=CORRELATION+':TransferInvestigationAgent',investigationSummary=agent['investigationSummary'],
        overallRiskLevel=agent['overallRiskLevel'],documentEvidenceStatus=agent['documentEvidenceStatus'],proposedActions=actions)
    def call(node, method, path, data=None):
        r=client.request(method,path,headers=headers,json=data)
        assert r.status_code==200,r.text
        responses[node]=dict(code=r.status_code,body=r.json())
        return r.json()
    p=call('PreviewResolutionPlan','POST',root+'/resolution-plans/preview',body)
    path=root+'/resolution-plans/'+p['planId']
    binding={k:p[k] for k in ('planHash','planVersion')}
    decision=dict(binding,reviewOutcome=outcome,reviewerReference=REVIEWER,reviewerComments='TEST ONLY',
        additionalInformation='',reviewEventReference=CORRELATION+':TransferOperationsReview')
    call('RecordReviewDecision','POST',path+'/decision',decision)
    call('ExecuteDemoDisposition','POST',path+'/execute',binding)
    call('ReadResolutionPlan','GET',path)
    call('ReadLatestReconciliation','GET',root+'/reconciliation')
    call('VerifyDemoDisposition','GET',path+'/verify')
    call('ReadReviewAudit','GET',path+'/audit')
    human=dict(outcome=PORTS[LABELS[outcome]],output=dict(Action=LABELS[outcome],reviewerComments='TEST ONLY',additionalInformation=''))
    return responses,dict(localTransport=True,agentTestDouble=agent,humanTestDouble=human,
        reviewerReference=REVIEWER,testCorrelationId=CORRELATION)


@pytest.mark.parametrize('tid,outcome', [('TRF-1002',x) for x in LABELS]+[('TRF-1004','APPROVE'),('TRF-1005','APPROVE')])
def test_review_graph_against_real_backend_responses(client,tid,outcome):
    responses,options=review_responses(client,tid,outcome)
    result=run_graph(tid,responses,**options)
    assert result['result']['workflowOutcome']==responses['VerifyDemoDisposition']['body']['workflowOutcome'],(result['result'].get('error'),result['trace'])
    assert result['result']['verificationStatus']=='VERIFIED_DEMO_STATE'
    assert FORM['id'] in result['trace']
    assert 'CorporateActionExtractor' not in result['trace']
    assert len(result['calls'])==14
    assert 'reviewCapability' not in json.dumps(result['result'])


def test_review_graph_failures_and_tampering_fail_closed(client):
    responses,options=review_responses(client,'TRF-1002','APPROVE')
    for node in ('PreviewResolutionPlan','RecordReviewDecision','ExecuteDemoDisposition','ReadResolutionPlan','ReadLatestReconciliation','VerifyDemoDisposition','ReadReviewAudit'):
        run=run_graph('TRF-1002',responses,**options,fault=dict(nodeId=node,status=503))
        assert run['result']['workflowOutcome']=='REVIEW_FAILED',run
    changes=[('PreviewResolutionPlan','planHash','bad'),('ReadResolutionPlan','status','PREVIEWED'),
             ('VerifyDemoDisposition','positionsUnchanged',False),('ReadLatestReconciliation','inputFingerprint','changed'),
             ('ReadReviewAudit','items',[])]
    for node,key,value in changes:
        altered=copy.deepcopy(responses);altered[node]['body'][key]=value
        assert run_graph('TRF-1002',altered,**options)['result']['workflowOutcome']=='REVIEW_FAILED'
    options['humanTestDouble']['output']['Action']='Reject'
    assert run_graph('TRF-1002',responses,**options)['result']['workflowOutcome']=='REVIEW_FAILED'


@pytest.mark.parametrize('outcome', ['APPROVE', 'REJECT'])
@pytest.mark.parametrize('field', ['comments', 'reviewerCommentsOptional', 'Reviewer comments (optional)'])
def test_review_lowercase_comments_are_validated(client, outcome, field):
    responses, options = review_responses(client, 'TRF-1002', outcome)
    human = options['humanTestDouble']['output']
    human[field] = human.pop('reviewerComments')
    result = run_graph('TRF-1002', responses, **options)
    assert result['result']['verificationStatus'] == 'VERIFIED_DEMO_STATE'
    # New form output must be consumed and validated, not silently ignored.
    human[field] = {'unexpected': 'object'}
    failed = run_graph('TRF-1002', responses, **options)
    assert failed['result']['workflowOutcome'] == 'REVIEW_FAILED'
    assert 'RecordReviewDecision' not in failed['trace']


def test_manual_form_contract_and_both_outcome_ports():
    flow=json.loads(FLOW.read_text())
    node=next(n for n in flow['nodes'] if n['id']==FORM['id'])
    assert node['inputs']['schema']['type']=='hitl-schema'
    assert {o['name'] for o in node['inputs']['schema']['outcomes']}=={'Approve','Reject'}
    assert all(o['action']=='Continue' for o in node['inputs']['schema']['outcomes'])
    edges={e['sourcePort']:e['targetNodeId'] for e in flow['edges'] if e['sourceNodeId']==node['id']}
    assert edges=={'outcome-'+PORTS['Approve']:'ApproveDisposition','outcome-'+PORTS['Reject']:'RejectDisposition'}
    fields=node['inputs']['schema']['fields']
    assert {f['id'] for f in fields if f['direction']=='output'}=={'reviewerCommentsOptional'}
    assert 'reviewCapability' not in json.dumps(node)


@pytest.mark.parametrize('label', ['Request Evidence', 'Escalate'])
def test_unsupported_manual_outcome_cannot_record_decision(client, label):
    responses, options=review_responses(client,'TRF-1002','APPROVE')
    options['humanTestDouble']['output']['Action']=label
    result=run_graph('TRF-1002',responses,**options)
    assert result['result']['workflowOutcome']=='REVIEW_FAILED'
    assert 'RecordReviewDecision' not in result['trace']


def test_edited_form_summary_cannot_change_validated_proposal(client):
    responses, options=review_responses(client,'TRF-1002','APPROVE')
    options['humanTestDouble']['output']['investigationSummaryFictionalDemoNoPositionChanges']='Forged: clear SEC-104 and change positions'
    result=run_graph('TRF-1002',responses,**options)
    assert result['result']['positionsUnchanged'] is True
    assert 'Forged' not in result['result']['investigationSummary']
