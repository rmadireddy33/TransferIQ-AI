"""Synthetic backend reviews and explicit test decisions; NOT real human approval."""
from uuid import uuid4
import pytest
from sqlalchemy import text


def setup(client, tid='TRF-1002'):
    created = client.post('/api/demo/runs/review', json={'transferId':tid}, headers={'Idempotency-Key':uuid4().hex})
    assert created.status_code == 201, created.text
    run = created.json()
    root = f"/api/demo/runs/{run['runId']}"
    r = client.post(root+'/reconcile', json={}).json()
    body = dict(transferId=tid,reconciliationRunId=r['reconciliationRunId'],agentInvestigationId='TEST-INVESTIGATION',
        investigationSummary='Explicit test fixture, not a model response',overallRiskLevel='MEDIUM',
        documentEvidenceStatus='NOT_PROCESSED_IXP_DISABLED',proposedActions=[dict(exceptionId=e['exceptionId'],
            securityId=e['securityId'],evidenceReferences=e['evidenceReferences'],
            disposition='ACCEPT_VERIFIED_EXPLANATION' if e['resolutionStatus']=='EXPLAINED' else
            ('OPEN_COST_BASIS_CASE' if e['exceptionType'].startswith('COST_BASIS_') else 'ESCALATE_TO_TRANSFER_OPERATIONS')) for e in r['exceptions']])
    headers={'X-Demo-Capability':run['reviewCapability'],'Idempotency-Key':uuid4().hex}
    return root, body, headers


def plan(client, tid='TRF-1002'):
    root, body, headers=setup(client,tid)
    response=client.post(root+'/resolution-plans/preview',json=body,headers=headers)
    assert response.status_code==200,response.text
    return root,body,headers,response.json()


def decision(p,outcome='APPROVE'):
    return dict(planVersion=p['planVersion'],planHash=p['planHash'],reviewOutcome=outcome,
        reviewerReference='UNVERIFIED_TEST_REFERENCE',reviewerComments='test-only',additionalInformation='',
        reviewEventReference='TEST-EVENT-'+uuid4().hex)


@pytest.mark.parametrize('outcome,expected', [('APPROVE','REVIEWED_WITH_OPEN_EXCEPTIONS'),
    ('REQUEST_EVIDENCE','EVIDENCE_REQUESTED'),('ESCALATE','ESCALATED'),('REJECT','REVIEW_REJECTED')])
def test_decision_execution_verify_and_audit(client,settings,outcome,expected):
    from tests.test_demo_execution import snapshot
    before=snapshot(settings.database_path)
    root,body,headers,p=plan(client)
    path=root+'/resolution-plans/'+p['planId']
    original=client.get(root+'/reconciliation').json()
    d=decision(p,outcome)
    assert client.post(path+'/decision',json=d,headers=headers).status_code==200
    assert client.post(path+'/decision',json=d,headers=headers).status_code==200
    binding={k:p[k] for k in ('planVersion','planHash')}
    for _ in range(2):
        assert client.post(path+'/execute',json=binding,headers=headers).status_code==200
    verification=client.get(path+'/verify').json()
    assert verification['workflowOutcome']==expected,verification
    assert verification['verificationStatus']=='VERIFIED_DEMO_STATE'
    assert verification['positionsUnchanged'] and not verification['transferCompleted']
    assert verification['unresolvedExceptions'][0]['securityId']=='SEC-104'
    assert verification['unresolvedExceptions'][0]['difference']=='-20'
    assert client.get(root+'/reconciliation').json()==original
    events=client.get(path+'/audit').json()
    assert len(events['items'])==3
    assert events['identityVerification']=='UNVERIFIED_DEMO_REFERENCE'
    assert len(verification['reviewedDispositions'])==(0 if outcome=='REJECT' else 2)
    assert snapshot(settings.database_path)==before
    conflicting=dict(d,reviewOutcome='REJECT' if outcome!='REJECT' else 'APPROVE')
    assert client.post(path+'/decision',json=conflicting,headers=headers).status_code==409


@pytest.mark.parametrize('change,status',[('exception',422),('action',422),('missing_evidence',422),
    ('wrong_evidence',422),('security',422),('stale_run',409),('foreign_transfer',404),('unsafe_accept',422)])
def test_invalid_plan_rejected(client,change,status):
    root,b,h=setup(client)
    if change=='exception':b['proposedActions'][0]['exceptionId']='EXC-WRONG'
    if change=='action':b['proposedActions'][0]['disposition']='APPLY_QUANTITY_CORRECTION'
    if change=='missing_evidence':b['proposedActions'][0]['evidenceReferences']=[]
    if change=='wrong_evidence':b['proposedActions'][0]['evidenceReferences']=['FAKE']
    if change=='security':b['proposedActions'][0]['securityId']='SEC-WRONG'
    if change=='stale_run':b['reconciliationRunId']='REC-WRONG'
    if change=='foreign_transfer':b['transferId']='TRF-1005'
    if change=='unsafe_accept':b['proposedActions'][1]['disposition']='ACCEPT_VERIFIED_EXPLANATION'
    assert client.post(root+'/resolution-plans/preview',json=b,headers=h).status_code==status


def test_idempotent_preview_binding_and_capability(client):
    root,b,h,p=plan(client)
    path=root+'/resolution-plans/'+p['planId']
    assert client.post(root+'/resolution-plans/preview',json=b,headers=h).json()['planId']==p['planId']
    b['investigationSummary']='Different'
    assert client.post(root+'/resolution-plans/preview',json=b,headers=h).status_code==409
    for field,value in [('planVersion',2),('planHash','0'*64)]:
        d=decision(p);d[field]=value
        assert client.post(path+'/decision',json=d,headers=h).status_code==409
    assert client.post(path+'/decision',json=decision(p)).status_code==403
    assert client.post(path+'/decision',json=decision(p),headers={'X-Demo-Capability':p['planHash']}).status_code==403
    root2,_,h2=setup(client,'TRF-1005')
    assert client.post(path+'/decision',json=decision(p),headers=h2).status_code==403
    assert client.get(root2+'/resolution-plans/'+p['planId']).status_code==404
    assert client.post(path+'/execute',json={k:p[k] for k in ('planVersion','planHash')},headers=h).status_code==409


def test_private_approval_does_not_trust_demo_reference(client,settings):
    for suffix in ('preview','fake/decision','fake/execute'):
        assert client.post('/api/resolution-plans/'+suffix,json={}).status_code==401
        assert client.post('/api/resolution-plans/'+suffix,json={},headers={'X-API-Key':settings.api_key.get_secret_value()}).status_code==503


@pytest.mark.parametrize('tid',['TRF-1004','TRF-1005'])
def test_basis_and_unsupported_shortage(client,tid):
    root,b,h,p=plan(client,tid)
    path=root+'/resolution-plans/'+p['planId']
    assert client.post(path+'/decision',json=decision(p),headers=h).status_code==200
    assert client.post(path+'/execute',json={k:p[k] for k in ('planVersion','planHash')},headers=h).status_code==200
    result=client.get(path+'/verify').json()
    assert result['unresolvedExceptions'] and result['positionsUnchanged']
    assert result['reviewedDispositions'][0]['disposition']==('OPEN_COST_BASIS_CASE' if tid=='TRF-1004' else 'ESCALATE_TO_TRANSFER_OPERATIONS')


def test_stale_data_and_immutable_plan(client,app):
    from sqlalchemy.exc import IntegrityError
    root,b,h,p=plan(client)
    run=root.rsplit('/',1)[-1]
    with app.state.demo_runs.open(run) as (_,_,session):
        with pytest.raises(IntegrityError):
            session.execute(text("UPDATE resolution_plans SET plan_hash='bad'"));session.commit()
        session.rollback()
        session.execute(text("UPDATE receiving_transfer_staging_positions SET quantity='99',version=2 WHERE security_id='SEC-104'"));session.commit()
    path=root+'/resolution-plans/'+p['planId']
    assert client.post(path+'/decision',json=decision(p),headers=h).status_code==409
    assert client.get(path+'/verify').status_code==409


def test_review_run_retry_and_expiry(client,app):
    key=uuid4().hex
    first=client.post('/api/demo/runs/review',json={'transferId':'TRF-1002'},headers={'Idempotency-Key':key})
    retry=client.post('/api/demo/runs/review',json={'transferId':'TRF-1002'},headers={'Idempotency-Key':key})
    assert retry.status_code==200 and retry.json()==first.json()
    assert client.post('/api/demo/runs',json={'transferId':'TRF-1002'},headers={'Idempotency-Key':key}).status_code==409
    with app.state.demo_runs.engine.begin() as conn:
        conn.execute(text('UPDATE demo_runs SET expires_at=0'))
    assert client.get('/api/demo/runs/'+first.json()['runId']+'/transfer').status_code==410


def test_review_restart_and_append_only_history(client,app,settings):
    from fastapi.testclient import TestClient
    from backend.main import create_app
    from sqlalchemy.exc import IntegrityError
    root,b,h,p=plan(client)
    path=root+'/resolution-plans/'+p['planId']
    client.post(path+'/decision',json=decision(p),headers=h).raise_for_status()
    client.post(path+'/execute',json={k:p[k] for k in ('planVersion','planHash')},headers=h).raise_for_status()
    expected=client.get(path+'/verify').json()
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(path+'/verify').json()==expected
        assert restarted.post(path+'/execute',json={k:p[k] for k in ('planVersion','planHash')},headers=h).status_code==200
    with app.state.demo_runs.open(root.rsplit('/',1)[-1]) as (_,_,session):
        for table in ('review_decisions','demo_dispositions','audit_events','position_snapshots'):
            for sql in (f'DELETE FROM {table}', f'INSERT OR REPLACE INTO {table} SELECT * FROM {table}'):
                with pytest.raises(IntegrityError):
                    session.execute(text(sql));session.commit()
                session.rollback()
    assert client.get(path+'/verify').json()==expected


def test_review_event_replay_quota_and_no_capability_disclosure(client):
    root,b,h,p=plan(client)
    d=decision(p)
    assert client.post(root+'/resolution-plans/'+p['planId']+'/decision',json=d,headers=h).status_code==200
    for i in range(4):
        h['Idempotency-Key']=uuid4().hex
        next_plan=client.post(root+'/resolution-plans/preview',json=b,headers=h).json()
        replay=dict(d,planHash=next_plan['planHash'])
        assert client.post(root+'/resolution-plans/'+next_plan['planId']+'/decision',json=replay,headers=h).status_code==409
    h['Idempotency-Key']=uuid4().hex
    assert client.post(root+'/resolution-plans/preview',json=b,headers=h).status_code==429
    for path in ('/transfer','/reconciliation','/resolution-plans/'+p['planId'],'/resolution-plans/'+p['planId']+'/audit'):
        assert h['X-Demo-Capability'] not in client.get(root+path).text


def test_registry_v1_migration_preserves_runs(client,app,settings):
    from backend.services.demo_runs import DemoRuns
    run=client.post('/api/demo/runs',json={'transferId':'TRF-1001'},headers={'Idempotency-Key':uuid4().hex}).json()
    with app.state.demo_runs.engine.begin() as conn:
        conn.exec_driver_sql('ALTER TABLE demo_runs DROP COLUMN review_token')
        conn.exec_driver_sql('PRAGMA user_version=1')
    migrated=DemoRuns(settings)
    try:
        with migrated.open(run['runId']) as (row,_,session):
            assert row['review_token'] is None
            assert row['transfer_id']=='TRF-1001'
    finally:
        migrated.engine.dispose()


def test_normal_run_cannot_gain_review_capability(client):
    key=uuid4().hex
    run=client.post('/api/demo/runs',json={'transferId':'TRF-1002'},headers={'Idempotency-Key':key}).json()
    assert client.post('/api/demo/runs/review',json={'transferId':'TRF-1002'},headers={'Idempotency-Key':key}).status_code==409
    assert client.post('/api/demo/runs/'+run['runId']+'/resolution-plans/preview',json={},headers={'Idempotency-Key':key}).status_code==403
