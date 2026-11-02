"""Real isolated backend responses through emitted JS/edges; NOT UiPath runtime tests."""
import copy
import json
from pathlib import Path
import subprocess

import pytest

from backend.database.seed import seed_demo

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / 'maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/TransferIQ_Reconciliation.flow'


def run_graph(transfer_id='TRF-1001', responses=None, **kwargs):
    result = subprocess.run(['node', str(ROOT / 'scripts/maestro-local-runner.mjs')],
        input=json.dumps(dict(transferId=transfer_id, responses=responses, **kwargs)),
        text=True, capture_output=True, check=True, timeout=15, cwd=ROOT)
    return json.loads(result.stdout)


def collect(client, auth, tid):
    def request(method, url):
        response = client.request(method, url, headers=auth, **({'json': {}} if method == 'POST' else {}))
        assert response.status_code in (200, 201)
        return dict(code=response.status_code, body=response.json())
    transfer = request('GET', f'/api/transfers/{tid}')
    body = transfer['body']
    return dict(GetTransferDetails=transfer,
        GetDeliveringPositions=request('GET', f"/api/delivering/accounts/{body['sourceAccountId']}/positions?limit=100&offset=0"),
        GetReceivingPositions=request('GET', f"/api/receiving/accounts/{body['destinationAccountId']}/positions?transferId={tid}&limit=100&offset=0"),
        RunReconciliation=request('POST', f'/api/transfers/{tid}/reconcile'))


@pytest.fixture
def scenarios(client, app, auth):
    seed_demo(app.state.session_factory, include_scenarios=True)
    return {f'TRF-{n}': collect(client, auth, f'TRF-{n}') for n in range(1001, 1006)}


@pytest.mark.parametrize('tid,direct,explained,unresolved,basis,outcome', [
    ('TRF-1001', 7, 0, 0, 0, 'CLEAN'),
    ('TRF-1002', 5, 1, 1, 0, 'INVESTIGATION_REQUIRED'),
    ('TRF-1003', 0, 1, 0, 0, 'CLEAN'),
    ('TRF-1004', 7, 0, 0, 1, 'CLEAN'),
    ('TRF-1005', 0, 0, 1, 0, 'INVESTIGATION_REQUIRED'),
])
def test_real_backend_contract(scenarios, tid, direct, explained, unresolved, basis, outcome):
    run = run_graph(tid, scenarios[tid], localTransport=True)
    result = run['result']
    assert result['workflowOutcome'] == outcome
    assert (result['directlyMatched'], result['evidenceExplained'], result['unresolvedCount'], result['costBasisIssues']) == (direct, explained, unresolved, basis)
    assert result['settledHoldings'] is False
    assert result['transferStatus'] == 'DRAFT'
    assert result['reconciliationRunId'] == scenarios[tid]['RunReconciliation']['body']['reconciliationRunId']
    assert run['trace'][-1] == ('CleanReconciliation' if not unresolved else 'InvestigationRequired')
    assert len(run['calls']) == 4
    assert 'transferId=' + tid in run['calls'][2]['path']
    if explained:
        assert result['evidenceReferences']
    if basis:
        assert result['requiresCostBasisReview'] is True
        assert result['costBasisExceptions'][0]['exceptionType'] == 'COST_BASIS_MISSING'


@pytest.mark.parametrize('tid', ['', None, 7, '../TRF-1001', 'a'*65, ' TRF-1001'])
def test_invalid_input_never_calls_http(tid):
    run = run_graph(tid)
    assert run['result']['workflowOutcome'] == 'FAILED'
    assert run['result']['error']['code'] == 'INVALID_TRANSFER_INPUT'
    assert run['calls'] == []


def test_unconfigured_artifact_fails_closed():
    run = run_graph()
    assert run['result']['error']['code'] == 'CONFIGURATION_REQUIRED'
    assert run['calls'] == []


@pytest.mark.parametrize('field', ['code', 'statusCode'])
def test_http_envelope_compatibility(scenarios, field):
    responses = copy.deepcopy(scenarios['TRF-1001'])
    for response in responses.values():
        status = response.pop('code')
        response[field] = status
    assert run_graph(responses=responses, localTransport=True)['result']['workflowOutcome'] == 'CLEAN'


@pytest.mark.parametrize('stage', ['GetTransferDetails', 'GetDeliveringPositions', 'GetReceivingPositions', 'RunReconciliation'])
@pytest.mark.parametrize('status', [401, 404, 422, 503, 0])
def test_error_edges_never_enter_clean(scenarios, stage, status):
    run = run_graph(responses=scenarios['TRF-1001'], localTransport=True, fault=dict(nodeId=stage, status=status))
    assert run['result']['workflowOutcome'] == 'FAILED'
    assert run['result']['error']['code'] == 'HTTP_REQUEST_FAILED'
    assert run['result']['correlation']['failedStep'] == stage
    assert 'RequiresInvestigation' not in run['trace']
    assert len([r for r in run['calls'] if r['nodeId'] == stage]) == (2 if status in (0, 503) else 1)


@pytest.mark.parametrize('change', [
    'body_null', 'body_string', 'empty_body', 'missing_summary', 'negative_count', 'string_count', 'bad_total',
    'wrong_transfer', 'incomplete_execution', 'positions_missing', 'exceptions_missing', 'false_clean',
    'missing_evidence', 'foreign_exception', 'duplicate_position', 'missing_quantity', 'wrong_basis_count',
])
def test_malformed_reconciliation_fails(scenarios, change):
    responses = copy.deepcopy(scenarios['TRF-1002'])
    r = responses['RunReconciliation']
    b = r['body']
    if change == 'body_null': r['body'] = None
    elif change == 'body_string': r['body'] = json.dumps(b)
    elif change == 'empty_body': r['body'] = {}
    elif change == 'missing_summary': del b['summary']
    elif change == 'negative_count': b['summary']['unresolved'] = -1
    elif change == 'string_count': b['summary']['unresolved'] = '1'
    elif change == 'bad_total': b['summary']['totalPositions'] = 99
    elif change == 'wrong_transfer': b['transferId'] = 'TRF-1001'
    elif change == 'incomplete_execution': b['executionStatus'] = 'FAILED'
    elif change == 'positions_missing': del b['positions']
    elif change == 'exceptions_missing': del b['exceptions']
    elif change == 'false_clean': b['summary']['unresolved'] = 0; b['summary']['directlyMatched'] = 6
    elif change == 'missing_evidence': next(p for p in b['positions'] if p['classification'] == 'EXPLAINED')['evidenceReferences'] = []
    elif change == 'foreign_exception': b['exceptions'][0]['transferId'] = 'TRF-OTHER'
    elif change == 'duplicate_position': b['positions'][0] = b['positions'][1]
    elif change == 'missing_quantity': del b['positions'][0]['sourceQuantity']
    elif change == 'wrong_basis_count': b['summary']['costBasisIssues'] = 1
    run = run_graph('TRF-1002', responses, localTransport=True)
    assert run['result']['workflowOutcome'] == 'FAILED'
    assert 'RequiresInvestigation' not in run['trace']


@pytest.mark.parametrize('stage,change', [
    ('GetTransferDetails', 'wrong_id'), ('GetTransferDetails', 'missing_status'),
    ('GetDeliveringPositions', 'empty'), ('GetDeliveringPositions', 'truncated'),
    ('GetReceivingPositions', 'truncated'), ('GetReceivingPositions', 'custody'),
    ('GetReceivingPositions', 'wrong_transfer'),
])
def test_invalid_context_stops_before_reconciliation(scenarios, stage, change):
    responses = copy.deepcopy(scenarios['TRF-1001'])
    body = responses[stage]['body']
    if change == 'wrong_id': body['transferId'] = 'TRF-OTHER'
    elif change == 'missing_status': del body['status']
    elif change == 'empty': body['items'] = []; body['total'] = 0
    elif change == 'truncated': body['total'] = 101
    elif change == 'custody': body['settledHoldings'] = True
    elif change == 'wrong_transfer': body['items'][0]['transferId'] = 'TRF-OTHER'
    run = run_graph(responses=responses, localTransport=True)
    assert run['result']['workflowOutcome'] == 'FAILED'
    assert 'RunReconciliation' not in run['trace']


def test_emitted_graph_integrity():
    flow = json.loads(FLOW.read_text())
    nodes = {n['id']: n for n in flow['nodes']}
    assert len(nodes) == len(flow['nodes'])
    reached = {'StartTransferInvestigation'}
    for _ in nodes:
        reached.update(e['targetNodeId'] for e in flow['edges'] if e['sourceNodeId'] in reached)
    assert reached == set(nodes)
    for e in flow['edges']:
        assert e['sourceNodeId'] in nodes and e['targetNodeId'] in nodes
    for n in nodes.values():
        if n['type'] == 'core.control.end': assert 'result' in n['outputs']
        if n['type'] == 'core.action.http.v2':
            assert n['inputs']['timeout'] == 'PT30S'
            assert n['inputs']['retryCount'] == 1
            assert n['inputs']['errorHandlingEnabled'] is True
            assert any(e['sourceNodeId'] == n['id'] and e['sourcePort'] == 'error' for e in flow['edges'])
            assert 'X-API-Key' not in n['inputs']['detail']['bodyParameters'].get('headers', {})
    assert nodes['StartTransferInvestigation']['display']['label'] == 'StartTransferInvestigation'
