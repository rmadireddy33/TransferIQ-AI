from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select, update

from backend.main import create_app
from backend.models.entities import Transfer
from backend.services.demo_runs import runs


def start(client, tid='TRF-1001', key=None):
    return client.post('/api/demo/runs', json={'transferId': tid},
                       headers={'Idempotency-Key': key or uuid4().hex})


def snapshot(path):
    with sqlite3.connect(path) as connection:
        return '\n'.join(connection.iterdump())


@pytest.mark.parametrize('tid,counts', [('TRF-1001', (7, 0, 0)), ('TRF-1002', (5, 1, 1)),
    ('TRF-1003', (0, 1, 0)), ('TRF-1004', (7, 0, 0)), ('TRF-1005', (0, 0, 1))])
def test_anonymous_actual_operations(client, app, settings, tid, counts):
    private_before = snapshot(settings.database_path)
    created = start(client, tid)
    assert created.status_code == 201, created.text
    run = created.json()['runId']
    root = f'/api/demo/runs/{run}'
    transfer = client.get(root + '/transfer')
    assert transfer.status_code == 200 and transfer.json()['transferId'] == tid
    body = transfer.json()
    source = f"{root}/delivering/accounts/{body['sourceAccountId']}/positions"
    target = f"{root}/receiving/accounts/{body['destinationAccountId']}/positions"
    before = [client.get(p).json() for p in (source, target)]
    assert all('items' in p for p in before)
    assert before[1]['settledHoldings'] is False
    result = client.post(root + '/reconcile', json={})
    assert result.status_code == 201, result.text
    summary = result.json()['summary']
    assert tuple(summary[k] for k in ('directlyMatched', 'evidenceExplained', 'unresolved')) == counts
    again = client.post(root + '/reconcile', json={})
    assert again.status_code == 200 and again.json()['reconciliationRunId'] == result.json()['reconciliationRunId']
    assert client.get(root + '/reconciliation').status_code == 200
    assert client.get(root + '/exceptions').status_code == 200
    docs = client.get(root + '/documents')
    assert docs.status_code == 200 and docs.json()['total'] >= 2
    doc = docs.json()['items'][0]
    pdf = client.get(root + '/documents/' + doc['documentId'] + '/download')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
    assert hashlib.sha256(pdf.content).hexdigest() == doc['checksumSha256']
    audit = client.get(root + '/audit').json()
    assert sum(x['action'] == 'RECONCILIATION_COMPLETED' for x in audit['items']) == 1
    assert audit['correctionsApplied'] == 0 and audit['maestroExecutionVerified'] is False
    assert [client.get(p).json() for p in (source, target)] == before
    assert snapshot(settings.database_path) == private_before
    assert 'storagePath' not in docs.text and 'API_KEY' not in docs.text


def test_retry_and_cross_run_isolation(client, app):
    key = uuid4().hex
    first = start(client, key=key).json()
    assert start(client, key=key).json() == first
    assert start(client, 'TRF-1002', key=key).status_code == 409
    second = start(client).json()
    assert second['runId'] != first['runId']
    a, b = [f"/api/demo/runs/{x['runId']}" for x in (first, second)]
    document = client.get(a + '/documents').json()['items'][0]['documentId']
    assert client.get(b + '/documents/' + document + '/download').status_code == 404
    assert client.get(a + '/delivering/accounts/ACC-SRC-1002/positions').status_code == 404
    assert client.get(a + '/receiving/accounts/ACC-DST-1002/positions').status_code == 404
    client.post(a + '/reconcile', json={})
    assert client.get(b + '/reconciliation').status_code == 404
    assert client.post(a + '/reconcile', json={'quantity': 999}).status_code == 422


def test_concurrent_idempotency(client, app):
    key = uuid4().hex
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: start(client, key=key), range(3)))
    # A bounded lock can return 503 while the first caller generates PDFs.
    # Retry only after the concurrent batch finishes, using the same request ID.
    assert all(r.status_code in (200, 201, 503) for r in results)
    results = [start(client, key=key) if r.status_code == 503 else r for r in results]
    assert sorted(r.status_code for r in results) == [200, 200, 201]
    assert len({r.json()['runId'] for r in results}) == 1
    root = '/api/demo/runs/' + results[0].json()['runId']
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: client.post(root + '/reconcile', json={}), range(3)))
    assert sorted(r.status_code for r in results) == [200, 200, 201]
    assert len({r.json()['reconciliationRunId'] for r in results}) == 1


def test_expiry_quota_and_restart(settings):
    settings = settings.model_copy(update={'demo_max_runs': 1})
    app = create_app(settings)
    with TestClient(app) as client:
        run = start(client).json()['runId']
        assert start(client).status_code == 429
        root = '/api/demo/runs/' + run
        result = client.post(root + '/reconcile', json={}).json()['reconciliationRunId']
    restarted = create_app(settings)
    with TestClient(restarted) as client:
        assert client.get(root + '/reconciliation').json()['reconciliationRunId'] == result
        with restarted.state.demo_runs.engine.begin() as connection:
            connection.execute(update(runs).values(expires_at=time.time() - 1))
        assert client.get(root + '/transfer').status_code == 410
        expired_dir = restarted.state.demo_runs.run_settings(run).data_dir
        assert start(client).status_code == 201
        assert not expired_dir.exists()
        assert settings.database_path.exists()


def test_no_mutation_escape_or_arbitrary_inputs(client):
    assert start(client, 'TRF-PRIVATE').status_code == 422
    assert client.post('/api/demo/runs', json={'transferId': 'TRF-1001'}).status_code == 422
    run = start(client).json()['runId']
    root = '/api/demo/runs/' + run
    for path in ('/reset', '/approve', '/correct', '/trigger', '/documents'):
        assert client.post(root + path, json={}).status_code in (404, 405)
    assert client.post('/api/transfers/TRF-1001/reconcile', json={}).status_code == 401
    assert client.post('/api/transfers/TRF-1001/documents').status_code == 401
    assert client.patch('/api/transfers/TRF-1001', json={}).status_code == 405
    assert client.post('/api/demo/runs', content=b'x' * 4097).status_code == 413
    assert client.post(root + '/reconcile', content=iter([b'x' * 4097]),
        headers={'Content-Type': 'application/json'}).status_code == 413


def test_disabled(settings):
    with TestClient(create_app(settings.model_copy(update={'demo_execution_enabled': False}))) as client:
        assert start(client).status_code == 404


def test_creation_rate_budget(client):
    for _ in range(5):
        assert start(client, 'NOT-A-DEMO').status_code == 422
    response = start(client)
    assert response.status_code == 429
    assert int(response.headers['retry-after']) > 0


def test_storage_admission_budget(settings):
    app = create_app(settings.model_copy(update={'demo_storage_limit_mb': 10}))
    with TestClient(app) as client:
        (app.state.demo_runs.root / 'quota-test.bin').write_bytes(b'x' * (6 * 1024 * 1024))
        assert start(client).status_code == 429


def test_busy_is_explicit_retriable_failure(client, app):
    app.state.demo_runs.lock.acquire()
    try:
        response = start(client)
        assert response.status_code == 503 and response.json()['detail']['code'] == 'demo_busy'
    finally:
        app.state.demo_runs.lock.release()
