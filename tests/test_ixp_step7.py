"""Backend/validator tests. IXP envelopes below are TEST DOUBLES, not extraction evidence."""
import copy
import json
from pathlib import Path
import subprocess

import pytest
from pypdf import PdfReader
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.main import create_app
from tests.test_maestro_contract import collect, run_graph

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'maestro/TransferIQ_Reconciliation/TransferIQ_Reconciliation/.flow-sdk/scripts/validate-corporate-action.js'


@pytest.fixture(scope='module')
def evidence(tmp_path_factory):
    with TestClient(create_app(Settings(data_dir=tmp_path_factory.mktemp('ixp-step7')))) as client:
        responses = collect(client, 'TRF-1002')
        run = responses['CreateDemoRun']['body']['runId']
        reference = client.get(f'/api/demo/runs/{run}/corporate-actions?limit=100&offset=0')
        assert reference.status_code == 200
        normalized = run_graph('TRF-1002', responses, localTransport=True)['result']
        # The expected scalar projection is a unit fixture only. The in-Flow
        # provider's actual nested result must be inspected before adapter signoff.
        extracted = dict(securityId='SEC-103', securityName='Fictional Scenario Security SEC-103',
            actionType='STOCK_SPLIT', splitNumerator=2, splitDenominator=1,
            effectiveDate='2026-08-10', noticeDate='2026-08-15', evidenceReference='CA-2026-081')
        envelope = dict(version='TEST_DOUBLE', type='TEST_DOUBLE', result=extracted, taxonomy={}, metadata={})
        return responses, dict(NormalizeReconciliation=dict(output=normalized),
            CorporateActionExtractor=dict(output=envelope),
            GetCorporateActionReference=dict(output=dict(code=200, body=reference.json())))


def validate(variables):
    command = "const fs=require('fs'),vm=require('vm'); const p=JSON.parse(fs.readFileSync(0,'utf8')); const code=fs.readFileSync(p.script,'utf8'); process.stdout.write(JSON.stringify(vm.runInNewContext('(function(){'+code+'\\n})()',{$vars:p.vars},{timeout:1000})));"
    r = subprocess.run(['node', '-e', command], input=json.dumps(dict(script=str(SCRIPT), vars=variables)),
                       text=True, capture_output=True, check=True, timeout=10)
    return json.loads(r.stdout)


def test_reference_is_scoped_read_only_and_independent(client, settings):
    from tests.test_demo_execution import start, snapshot
    before = snapshot(settings.database_path)
    run = start(client, 'TRF-1002').json()['runId']
    path = f'/api/demo/runs/{run}/corporate-actions'
    response = client.get(path)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    data = response.json()
    assert data['transferId'] == 'TRF-1002' and data['runId'] == run
    assert data['referenceSource'] == 'SEEDED_REFERENCE_DATABASE'
    assert data['total'] == 1
    action = data['items'][0]
    assert (action['securityId'], action['actionType'], action['numerator'], action['denominator']) == ('SEC-103', 'SPLIT', 2, 1)
    assert (action['effectiveDate'], action['noticeDate'], action['evidenceReference']) == ('2026-08-10', '2026-08-15', 'CA-2026-081')
    assert client.get(path + '?limit=1&offset=1').json()['items'] == []
    assert client.get(path + '?limit=101').status_code == 422
    assert client.get('/api/demo/runs/DEMO-unknown/corporate-actions').status_code == 404
    other = start(client, 'TRF-1001').json()['runId']
    assert client.get(f'/api/demo/runs/{other}/corporate-actions').json()['items'] == []
    assert client.get('/api/corporate-actions').status_code == 401
    for method in ('post', 'put', 'patch', 'delete'):
        assert client.request(method, path).status_code == 405
    assert snapshot(settings.database_path) == before


def test_verified_fixture_does_not_clear_investigation_or_positions(evidence):
    _, variables = evidence
    result = validate(variables)
    assert result['extractionResult']['extractionStatus'] == 'VERIFIED'
    assert result['workflowOutcome'] == 'INVESTIGATION_REQUIRED' and result['unresolvedCount'] == 1
    for key in ('sourcePositions', 'receivingStagingPositions', 'exceptions', 'reconciliationRunId'):
        assert result[key] == variables['NormalizeReconciliation']['output'][key]


@pytest.mark.parametrize('field,value', [
    ('securityId', 'SEC-107'), ('securityName', 'Different security'), ('actionType', 'DIVIDEND'),
    ('splitDenominator', 0), ('splitDenominator', '1'), ('splitNumerator', 1.5),
    ('splitNumerator', 1000000001), ('splitNumerator', 3), ('splitDenominator', None),
    ('effectiveDate', '2026-02-30'), ('effectiveDate', '2026-08-11'), ('noticeDate', 'today'),
    ('evidenceReference', 'CA-OTHER'), ('securityId', {'value': 'SEC-103'}),
])
def test_bad_extraction_requires_review(evidence, field, value):
    variables = copy.deepcopy(evidence[1])
    variables['CorporateActionExtractor']['output']['result'][field] = value
    result = validate(variables)
    assert result['extractionResult']['extractionStatus'] == 'REVIEW_REQUIRED'
    assert result['extractionResult']['discrepancies']
    assert result['workflowOutcome'] == 'INVESTIGATION_REQUIRED'
    assert result['evidenceOutcome'] == 'EVIDENCE_REVIEW_REQUIRED'


@pytest.mark.parametrize('output', [None, {}, [], {'error': True}, {'ExtractionResult': {}}, {'result': {}}])
def test_missing_or_unknown_ixp_envelope_fails_closed(evidence, output):
    variables = copy.deepcopy(evidence[1])
    variables['CorporateActionExtractor'] = dict(output=output)
    assert validate(variables)['extractionResult']['extractionStatus'] == 'EXTRACTION_FAILED'


@pytest.mark.parametrize('change', ['wrong_transfer', 'wrong_run', 'unverified', 'no_reference', 'duplicate', 'truncated', 'http_failure'])
def test_independent_reference_must_agree(evidence, change):
    variables = copy.deepcopy(evidence[1])
    response = variables['GetCorporateActionReference']['output']
    body = response['body']
    if change == 'wrong_transfer': body['transferId'] = 'TRF-1001'
    elif change == 'wrong_run': body['runId'] = 'another-run'
    elif change == 'unverified': body['items'][0]['verified'] = False
    elif change == 'no_reference': body.update(items=[], total=0)
    elif change == 'duplicate': body['items'] *= 2; body['total'] = 2
    elif change == 'truncated': body['total'] = 2
    elif change == 'http_failure': response['code'] = 503
    assert validate(variables)['extractionResult']['extractionStatus'] == 'REVIEW_REQUIRED'


def test_missing_file_and_setup_stop_are_explicit(evidence):
    responses, _ = evidence
    missing = run_graph('TRF-1002', responses, localTransport=True)
    assert missing['result']['evidenceOutcome'] == 'EVIDENCE_UNAVAILABLE'
    assert 'CorporateActionExtractor' not in missing['trace']
    # This checks the configuration failure route; it DOES NOT call IXP.
    supplied = run_graph('TRF-1002', responses, localTransport=True, corporateActionPdf={'ID': 'TEST_FILE'})
    assert supplied['trace'][-1] == 'ExtractionFailed'
    assert supplied['result']['extractionResult']['extractionStatus'] == 'EXTRACTION_FAILED'
    assert supplied['result']['workflowOutcome'] == 'INVESTIGATION_REQUIRED'


def test_confidence_is_not_validation(evidence):
    variables = copy.deepcopy(evidence[1])
    variables['CorporateActionExtractor']['output']['metadata'] = dict(confidence=1.0)
    variables['CorporateActionExtractor']['output']['result']['securityId'] = 'SEC-WRONG'
    assert validate(variables)['extractionResult']['extractionStatus'] == 'REVIEW_REQUIRED'
