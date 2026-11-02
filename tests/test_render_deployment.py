"""Render configuration checks; disk detection is mocked, not a live cloud test."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.core.config import Settings
from backend.core.runtime import validate_runtime_environment
from backend.main import create_app
from backend.start import server_options


def render_settings(settings):
    return settings.model_copy(update={'app_env': 'production', 'data_dir': Path('/data').resolve()})


def test_render_requires_mounted_disk(settings, monkeypatch):
    settings = render_settings(settings)
    env = {'RENDER': 'true', 'DATA_DIR': '/data'}
    monkeypatch.setattr(Path, 'is_mount', lambda self: False)
    with pytest.raises(RuntimeError, match='Render persistent disk'):
        validate_runtime_environment(settings, env)
    monkeypatch.setattr(Path, 'is_mount', lambda self: True)
    validate_runtime_environment(settings, env)  # No Railway-specific variables required.


@pytest.mark.parametrize('data_dir', [None, './data', '/tmp', '/data/other'])
def test_render_rejects_nonpersistent_configuration(settings, data_dir):
    env = {'RENDER': 'true'}
    if data_dir is not None:
        env['DATA_DIR'] = data_dir
    with pytest.raises(RuntimeError, match='Render requires DATA_DIR=/data'):
        validate_runtime_environment(render_settings(settings), env)


def test_render_requires_production_and_secret(settings):
    env = {'RENDER': 'true', 'DATA_DIR': '/data'}
    with pytest.raises(RuntimeError, match='APP_ENV=production'):
        validate_runtime_environment(settings, env)
    settings = render_settings(settings).model_copy(update={'api_key': SecretStr('')})
    with pytest.raises(RuntimeError, match='API_KEY'):
        validate_runtime_environment(settings, env)


def test_render_wrong_disk_fails_before_storage_is_created(settings, monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('DATA_DIR', str(settings.data_dir))
    settings = settings.model_copy(update={'app_env': 'production'})
    app = create_app(settings)
    with pytest.raises(RuntimeError, match='configuration'):
        with TestClient(app):
            pass
    assert not settings.data_dir.exists()
    assert app.state.ready is False


def test_render_configuration_never_reads_local_dotenv(monkeypatch, tmp_path):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.delenv('RAILWAY_ENVIRONMENT_ID', raising=False)
    monkeypatch.delenv('API_KEY', raising=False)
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    def forbidden(*args, **kwargs):
        raise AssertionError('Render must use environment secrets, not a local .env')
    monkeypatch.setattr('backend.core.config.dotenv_values', forbidden)
    assert Settings.from_environment().api_key.get_secret_value() == ''


def test_render_port_and_single_worker():
    options = server_options({'RENDER': 'true', 'PORT': '10000', 'WEB_CONCURRENCY': '8',
                              'RENDER_WEB_CONCURRENCY': '8'})
    assert options['app'] == 'backend.main:app'
    assert options['host'] == '0.0.0.0'
    assert options['port'] == 10000
    assert options['workers'] == 1
    assert options['reload'] is False
