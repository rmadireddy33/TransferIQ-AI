import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.api.judging import catalog
from backend.api.public_limits import PublicRequestBudget
from backend.main import create_app
from backend.models.entities import Client, ReceivingTransferStagingPosition, Transfer
from backend.models.reconciliation import ReconciliationRun
from scripts.build_judging_samples import build_catalog


def test_fixture_matches_real_engine_in_isolated_database(tmp_path):
    assert build_catalog(tmp_path / 'generation') == catalog()


def test_public_catalog_is_precomputed_not_live(client, app, auth, transfer_payload):
    before = client.get('/api/demo/transfers').json()
    assert before['evidenceMode'] == 'PRECOMPUTED_SYNTHETIC_SAMPLE'
    assert len(before['items']) == 5
    with app.state.session_factory.begin() as session:
        session.get(Client, 'CLI-001').first_name = 'PRIVATE-SENTINEL'
        session.get(ReceivingTransferStagingPosition, 'STG-001').quantity = 999
    created = client.post('/api/transfers', headers=auth, json=transfer_payload).json()
    response = client.get('/api/demo/transfers')
    assert response.json() == before
    assert 'PRIVATE-SENTINEL' not in response.text
    assert created['transferId'] not in response.text
    assert client.get('/api/demo/transfers/' + created['transferId']).status_code == 404
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ReconciliationRun)) == 0
    for sample in before['items']:
        assert sample['liveExecution'] is False and sample['reconciliationRunId'] is None
        assert sample['quantityReconciliationOnly'] is True
        assert client.get('/api/demo/transfers/' + sample['transferId']).json() == sample
    basis = client.get('/api/demo/transfers/TRF-1004').json()
    assert basis['expectedWorkflowOutcome'] == 'CLEAN'
    assert basis['requiresCostBasisReview'] is True
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['cache-control'] == 'public, max-age=60'


def test_public_routes_do_not_open_database(client, app, monkeypatch):
    def forbidden():
        raise AssertionError('Public samples must never query live storage')
    monkeypatch.setattr(app.state, 'session_factory', forbidden)
    assert client.get('/api/demo/transfers').status_code == 200
    assert client.get('/api/demo/transfers/TRF-1002').status_code == 200


@pytest.mark.parametrize('path', [
    '/api/clients', '/api/clients/CLI-001', '/api/firms', '/api/accounts/ACC-SRC-001',
    '/api/securities', '/api/securities/SEC-001', '/api/transfers', '/api/transfers/TRF-1001',
    '/api/transfers/TRF-1001/assets', '/api/delivering/accounts/ACC-SRC-001/positions',
    '/api/receiving/accounts/ACC-DST-001/positions', '/api/transfers/TRF-1001/reconciliation',
    '/api/transfers/TRF-1001/exceptions', '/api/corporate-actions', '/api/reconciliation-runs/unknown',
    '/api/transfers/TRF-1001/documents', '/api/documents/unknown', '/api/documents/unknown/download',
])
def test_live_reads_require_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={'X-API-Key': 'wrong'}).status_code == 401


@pytest.mark.parametrize('path', ['/api/transfers', '/api/transfers/TRF-1001/reconcile',
                                  '/api/transfers/TRF-1001/documents'])
def test_mutations_remain_protected(client, path):
    assert client.post(path, json={}).status_code == 401


def test_openapi_security_inventory(client):
    spec = client.get('/openapi.json').json()
    public = {'/health', '/api/demo/transfers', '/api/demo/transfers/{transferId}',
        '/api/demo/runs', '/api/demo/runs/{runId}/transfer',
        '/api/demo/runs/{runId}/delivering/accounts/{accountId}/positions',
        '/api/demo/runs/{runId}/receiving/accounts/{accountId}/positions',
        '/api/demo/runs/{runId}/reconcile', '/api/demo/runs/{runId}/reconciliation',
        '/api/demo/runs/{runId}/exceptions', '/api/demo/runs/{runId}/documents',
        '/api/demo/runs/{runId}/documents/{documentId}/download', '/api/demo/runs/{runId}/audit'}
    for path, methods in spec['paths'].items():
        for operation in methods.values():
            if path in public:
                assert not operation.get('security')
            else:
                assert operation['security'] == [{'APIKeyHeader': []}], path


@pytest.mark.parametrize('path', ['/api/demo/transfers/TRF-9999', '/data/transferiq.db', '/.env',
    '/api/demo/documents', '/api/demo/logs', '/api/demo/transfers/TRF-1001/reconcile'])
def test_no_private_file_or_admin_routes(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
def test_public_view_has_no_mutations(client, method):
    assert getattr(client, method)('/api/demo/transfers/TRF-1001').status_code == 405


def test_disabled_and_unconfigured_key_fail_closed(settings):
    with TestClient(create_app(settings.model_copy(update={'public_demo_enabled': False}))) as client:
        assert client.get('/api/demo/transfers').status_code == 404
        assert client.get('/health').status_code == 200
    with TestClient(create_app(settings.model_copy(update={'api_key': type(settings.api_key)('')}))) as client:
        assert client.get('/api/demo/transfers').status_code == 200
        assert client.get('/api/transfers').status_code == 503
        assert client.post('/api/transfers/TRF-1001/reconcile').status_code == 503


def test_rate_limit_ignores_spoofed_headers_and_key(settings):
    settings = settings.model_copy(update={'public_demo_requests_per_minute': 2})
    with TestClient(create_app(settings)) as client:
        for n in range(2):
            assert client.get('/api/demo/transfers', headers={'X-Forwarded-For': f'1.2.3.{n}'}).status_code == 200
        denied = client.get('/api/demo/transfers', headers={'X-Forwarded-For': '9.9.9.9',
            'X-API-Key': settings.api_key.get_secret_value()})
        assert denied.status_code == 429 and int(denied.headers['retry-after']) > 0
        assert denied.headers['cache-control'] == 'no-store'
        assert client.get('/health').status_code == 200
        assert client.get('/api/transfers', headers={'X-API-Key': settings.api_key.get_secret_value()}).status_code == 200


def test_global_budget_and_window_expiry(monkeypatch):
    now = [100.0]
    monkeypatch.setattr('backend.api.public_limits.time.monotonic', lambda: now[0])
    budget = PublicRequestBudget()
    for n in range(3):
        assert budget.allow(str(n), 60, 3)[0]
    assert not budget.allow('new-peer', 60, 3)[0]
    now[0] += 61
    assert budget.allow('new-peer', 60, 3)[0]
    for n in range(2500):
        budget.allow(str(n), 600, 3000)
    assert len(budget.clients) <= 2048


def test_public_request_size_limits(client):
    assert client.get('/api/demo/transfers?' + 'x' * 1025).status_code == 414
    assert client.request('GET', '/api/demo/transfers', content=b'not allowed').status_code == 413
    response = client.get('/api/demo/transfers')
    for forbidden in ('accountNumber', 'email', 'storagePath', 'documentId', 'API_KEY', '.env', 'REC-'):
        assert forbidden not in response.text
    assert len(response.content) < 40000
