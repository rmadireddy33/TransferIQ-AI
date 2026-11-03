"""Deployment startup, mounted-storage policy and real HTTP tests in temporary directories."""
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from backend.core.config import PROJECT_ROOT, Settings
from backend.core.logging import JsonFormatter
from backend.core.runtime import validate_runtime_environment
from backend.database import seed_documents as documents
from backend.database.session import create_database_engine
from backend.main import create_app
from backend.models.documents import TransferDocument
from backend.models.entities import Client
from backend.start import server_options


def seeded_settings(settings):
    return settings.model_copy(update={'seed_demo_data': True})


def snapshot_database(path):
    with sqlite3.connect(path) as connection:
        return '\n'.join(connection.iterdump())


def test_startup_seed_and_restart_preserve_every_row_and_file(settings, monkeypatch):
    settings = seeded_settings(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/api/transfers', headers={'X-API-Key': settings.api_key.get_secret_value()}).json()['total'] == 5
        with app.state.session_factory.begin() as session:
            session.get(Client, 'CLI-001').first_name = 'ChangedFictionalName'
        with app.state.session_factory() as session:
            assert len(session.scalars(select(TransferDocument)).all()) == 16
    before = snapshot_database(settings.database_path)
    files = {p.relative_to(settings.data_dir): p.read_bytes() for p in (settings.data_dir / 'documents').rglob('*.pdf')}
    def must_not_render(*args):
        raise AssertionError('An existing recipe must never be regenerated at startup')
    monkeypatch.setattr(documents, 'render_pdf', must_not_render)
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/clients/CLI-001', headers={'X-API-Key': settings.api_key.get_secret_value()}).json()['firstName'] == 'ChangedFictionalName'
    assert snapshot_database(settings.database_path) == before
    assert {p.relative_to(settings.data_dir): p.read_bytes() for p in (settings.data_dir / 'documents').rglob('*.pdf')} == files


def test_empty_volume_without_seed_stays_empty(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get('/health').json()['database'] == 'ok'
        assert client.get('/api/transfers', headers={'X-API-Key': settings.api_key.get_secret_value()}).json()['total'] == 0
    assert settings.database_path.exists()
    assert not list((settings.data_dir / 'documents').rglob('*.pdf'))


def test_missing_recipe_is_only_pdf_generated(settings, monkeypatch):
    settings = seeded_settings(settings)
    app = create_app(settings)
    with TestClient(app):
        with app.state.session_factory.begin() as session:
            # Simulate an interrupted initial seed; leave all other document IDs untouched.
            row = session.scalar(select(TransferDocument).where(TransferDocument.sample_key.like('TRF-1005:TRANSFER_REQUEST:%')))
            session.delete(row)
        with app.state.session_factory() as session:
            preserved = {r.document_id for r in session.scalars(select(TransferDocument))}
    real_render, calls = documents.render_pdf, []
    def counted(*args):
        calls.append(args[1])
        return real_render(*args)
    monkeypatch.setattr(documents, 'render_pdf', counted)
    restarted = create_app(settings)
    with TestClient(restarted):
        with restarted.state.session_factory() as session:
            current = {r.document_id for r in session.scalars(select(TransferDocument))}
        assert preserved.issubset(current) and len(current) == 16
    assert len(calls) == 1


def test_missing_registered_bytes_fail_instead_of_replacing_reference(settings):
    settings = seeded_settings(settings)
    with TestClient(create_app(settings)):
        pass
    next((settings.data_dir / 'documents').rglob('*.pdf')).unlink()
    before = snapshot_database(settings.database_path)
    with pytest.raises(RuntimeError, match='demo_documents'):
        with TestClient(create_app(settings)):
            pass
    assert snapshot_database(settings.database_path) == before


def test_startup_schema_failure_does_not_seed_or_reset(settings):
    engine = create_database_engine(settings)
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE keep_me (value TEXT)')
        connection.exec_driver_sql("INSERT INTO keep_me VALUES ('fictional sentinel')")
        connection.exec_driver_sql('PRAGMA user_version=99')
    engine.dispose()
    before = snapshot_database(settings.database_path)
    app = create_app(seeded_settings(settings))
    with pytest.raises(RuntimeError, match='schema'):
        with TestClient(app):
            pass
    assert app.state.ready is False
    assert snapshot_database(settings.database_path) == before


def test_readiness_and_temporary_upload_directory(settings):
    previous = tempfile.tempdir
    app = create_app(settings)
    with TestClient(app) as client:
        assert Path(tempfile.gettempdir()) == settings.data_dir / 'tmp'
        assert client.get('/health').status_code == 200
        app.state.ready = False
        assert client.get('/health').status_code == 503
    assert tempfile.tempdir == previous


def test_production_requires_key_before_creating_storage(settings):
    settings = settings.model_copy(update={'app_env': 'production', 'api_key': Settings().api_key})
    with pytest.raises(RuntimeError, match='API_KEY'):
        validate_runtime_environment(settings, {})
    assert not settings.data_dir.exists()


def test_railway_rejects_ephemeral_storage(settings):
    env = dict(RAILWAY_ENVIRONMENT_ID='test', DATA_DIR='/data', RAILWAY_VOLUME_MOUNT_PATH='/data')
    settings = settings.model_copy(update={'app_env': 'production'})
    with pytest.raises(RuntimeError, match='DATA_DIR'):
        validate_runtime_environment(settings, env)


def test_railway_requires_real_mount(settings, monkeypatch):
    settings = settings.model_copy(update={'app_env': 'production', 'data_dir': Path('/data').resolve()})
    env = dict(RAILWAY_ENVIRONMENT_ID='test', DATA_DIR='/data', RAILWAY_VOLUME_MOUNT_PATH='/data')
    monkeypatch.setattr(Path, 'is_mount', lambda self: False)
    with pytest.raises(RuntimeError, match='mounted'):
        validate_runtime_environment(settings, env)
    monkeypatch.setattr(Path, 'is_mount', lambda self: True)
    validate_runtime_environment(settings, env)  # Mocked mount-policy unit check, no filesystem changes.
    env.pop('RAILWAY_VOLUME_MOUNT_PATH')
    with pytest.raises(RuntimeError, match='mounted'):
        validate_runtime_environment(settings, env)


@pytest.mark.parametrize('value', ['true', '', 'yes', '2', 'False'])
def test_seed_flag_is_explicit(value, settings):
    with pytest.raises(ValidationError):
        Settings(data_dir=settings.data_dir, seed_demo_data=value)


def test_cloud_does_not_load_dotenv(monkeypatch, tmp_path):
    monkeypatch.setenv('RAILWAY_ENVIRONMENT_ID', 'test')
    monkeypatch.delenv('API_KEY', raising=False)
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    assert Settings.from_environment().api_key.get_secret_value() == ''


@pytest.mark.parametrize('port', ['0', '65536', 'bad', '-1', ''])
def test_invalid_start_port(port):
    with pytest.raises(ValueError):
        server_options({'PORT': port})


def test_start_command_and_railway_config():
    options = server_options({'PORT': '9000', 'WEB_CONCURRENCY': '8'})
    assert (options['app'], options['host'], options['port'], options['workers'], options['reload']) == ('backend.main:app', '0.0.0.0', 9000, 1, False)
    config = json.loads((PROJECT_ROOT / 'railway.json').read_text())
    assert config['build'] == {'builder': 'RAILPACK'}
    assert config['deploy']['startCommand'] == 'python -m backend.start'
    assert config['deploy']['requiredMountPath'] == '/data'
    assert config['deploy']['numReplicas'] == 1
    assert 'preDeployCommand' not in config['deploy']
    railpack = json.loads((PROJECT_ROOT / 'railpack.json').read_text())
    assert {'local': True, 'include': ['backend/requirements.txt']} in railpack['steps']['install']['inputs']


def test_json_logs_omit_exception_details():
    record = logging.LogRecord('transferiq', logging.ERROR, '', 0, 'startup_failed', (), None)
    try:
        raise ValueError('SECRET-DO-NOT-LOG')
    except ValueError:
        record.exc_info = sys.exc_info()
    result = JsonFormatter().format(record)
    assert 'SECRET-DO-NOT-LOG' not in result
    assert json.loads(result)['error_type'] == 'ValueError'
    record.msg = 'Traceback (most recent call last): SECRET-DO-NOT-LOG'
    assert 'SECRET-DO-NOT-LOG' not in JsonFormatter().format(record)


def test_default_exports_under_data_dir(settings):
    settings = seeded_settings(settings)
    app = create_app(settings)
    with TestClient(app):
        _, manifest = documents.seed_documents(app.state.session_factory, settings)
    assert (settings.data_dir / 'sample_exports/manifest.json').is_file()
    assert all(Path(row['samplePath']).is_relative_to(settings.data_dir) for row in manifest)


def test_real_start_restart_http_smoke(tmp_path, transfer_payload):
    """Execute the exact entry point twice, with real sockets and isolated persistent storage."""
    with socket.socket() as available:
        available.bind(('127.0.0.1', 0))
        port = available.getsockname()[1]
    key = secrets.token_urlsafe(32)
    env = {k: v for k, v in os.environ.items() if not k.startswith('RAILWAY_')}
    env.update(DATA_DIR=str(tmp_path / 'volume'), APP_ENV='production', API_KEY=key,
               SEED_DEMO_DATA='1', PORT=str(port), PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    headers = {'X-API-Key': key}
    saved_transfer = None
    saved_document = None
    saved_pdf = None
    saved_run = None
    for attempt in (1, 2):
        logfile = tmp_path / f'startup-{attempt}.jsonl'
        with logfile.open('w', encoding='utf-8') as output:
            process = subprocess.Popen([sys.executable, '-m', 'backend.start'], cwd=PROJECT_ROOT,
                                       env=env, stdout=output, stderr=subprocess.STDOUT)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10) as client:
                    deadline = time.monotonic() + 45
                    while True:
                        assert process.poll() is None, 'Startup exited early; inspect isolated test logs'
                        try:
                            if client.get('/health').status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        assert time.monotonic() < deadline, 'Startup readiness timed out'
                        time.sleep(0.1)
                    assert client.get('/docs').status_code == 200
                    public = client.get('/api/demo/transfers')
                    assert public.status_code == 200 and len(public.json()['items']) == 5
                    assert public.json()['evidenceMode'] == 'PRECOMPUTED_SYNTHETIC_SAMPLE'
                    assert client.get('/api/transfers/TRF-1001').status_code == 401
                    for n in range(1001, 1006):
                        assert client.get(f'/api/transfers/TRF-{n}', headers=headers).status_code == 200
                    assert client.post('/api/transfers', json=transfer_payload).status_code == 401
                    assert client.post('/api/transfers/TRF-1002/reconcile', json={}).status_code == 401
                    assert client.get('/api/transfers/TRF-1002/reconciliation').status_code == 401
                    if attempt == 1:
                        from scripts.verify_public_demo import verify
                        assert verify(f'http://127.0.0.1:{port}')['status'] == 'PASSED'
                        created = client.post('/api/transfers', headers=headers, json=transfer_payload)
                        assert created.status_code == 201
                        saved_transfer = created.json()
                        reconciled = client.post('/api/transfers/TRF-1002/reconcile', headers=headers, json={})
                        assert reconciled.status_code == 201
                        saved_run = reconciled.json()['reconciliationRunId']
                        assert reconciled.json()['summary']['unresolved'] == 1
                        samples = client.get('/api/transfers/TRF-1002/documents', headers=headers).json()['items']
                        source_doc = samples[0]
                        saved_pdf = client.get(f"/api/documents/{source_doc['documentId']}/download", headers=headers).content
                        uploaded = client.post('/api/transfers/TRF-1002/documents', headers=headers,
                            data={'documentType': 'ACCOUNT_STATEMENT', 'documentSource': 'CLIENT_UPLOAD'},
                            files={'file': ('fictional-persistence.pdf', saved_pdf, 'application/pdf')})
                        assert uploaded.status_code == 201
                        saved_document = uploaded.json()
                    else:
                        assert client.get(f"/api/transfers/{saved_transfer['transferId']}", headers=headers).json() == saved_transfer
                        assert client.get(f"/api/documents/{saved_document['documentId']}", headers=headers).json() == saved_document
                        replay = client.post('/api/transfers/TRF-1002/reconcile', headers=headers, json={})
                        assert replay.status_code == 200 and replay.json()['reconciliationRunId'] == saved_run
                    download = f"/api/documents/{saved_document['documentId']}/download"
                    assert client.get(download).status_code == 401
                    binary = client.get(download, headers=headers)
                    assert binary.status_code == 200 and binary.content == saved_pdf
                    assert hashlib.sha256(binary.content).hexdigest() == saved_document['checksumSha256']
            finally:
                process.terminate()
                process.wait(timeout=15)
        log = logfile.read_text(encoding='utf-8')
        assert key not in log
        entries = [json.loads(line) for line in log.splitlines() if line]
        seed_event = next(e for e in entries if e['event'] == 'fictional_demo_seed_complete')
        assert seed_event['seed_documents'] == (16 if attempt == 1 else 0)
        assert seed_event['seed_rows'] == (112 if attempt == 1 else 0)


def test_real_start_exits_nonzero_on_migration_failure(tmp_path):
    volume = tmp_path / 'volume'
    volume.mkdir()
    database = volume / 'transferiq.db'
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE keep_me (value TEXT)')
        connection.execute("INSERT INTO keep_me VALUES ('fictional sentinel')")
        connection.execute('PRAGMA user_version=99')
    before = snapshot_database(database)
    env = {k: v for k, v in os.environ.items() if not k.startswith('RAILWAY_')}
    key = secrets.token_urlsafe(32)
    env.update(DATA_DIR=str(volume), APP_ENV='production', API_KEY=key,
               SEED_DEMO_DATA='1', PORT='8000', PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-m', 'backend.start'], cwd=PROJECT_ROOT,
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert snapshot_database(database) == before
    log = result.stdout + result.stderr
    assert key not in log
    entries = [json.loads(line) for line in log.splitlines() if line]
    assert any(e['event'] == 'startup_failed' and e['phase'] == 'schema' for e in entries)
    assert not any(e['event'] == 'application_ready' for e in entries)
