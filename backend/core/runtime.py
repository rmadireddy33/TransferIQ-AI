"""Volume checks and temporary upload storage, executed at runtime only."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import re
from urllib.parse import urlparse

from backend.services.document_storage import private_path


def validate_runtime_environment(settings, environ=None):
    env = os.environ if environ is None else environ
    railway = bool(env.get('RAILWAY_ENVIRONMENT_ID'))
    render = env.get('RENDER') == 'true'
    if (railway or render or settings.app_env == 'production') and not settings.api_key.get_secret_value().strip():
        raise RuntimeError('Production requires API_KEY')
    if railway or render:
        platform = 'Render' if render else 'Railway'
        if settings.app_env != 'production':
            raise RuntimeError(f'{platform} requires APP_ENV=production')
        if env.get('DATA_DIR') != '/data' or settings.data_dir != Path('/data').resolve():
            raise RuntimeError(f'{platform} requires DATA_DIR=/data')
        if not settings.data_dir.is_mount():
            raise RuntimeError(f'{platform} persistent disk must be mounted at /data')
        if railway and env.get('RAILWAY_VOLUME_MOUNT_PATH') != '/data':
            raise RuntimeError('Railway persistent volume must be mounted at /data')
    if settings.portal_investigation_enabled:
        if not settings.demo_execution_enabled:
            raise RuntimeError('Portal investigation requires DEMO_EXECUTION_ENABLED=1')
        if len(settings.portal_operator_access_key.get_secret_value()) < 16:
            raise RuntimeError('Portal investigation requires PORTAL_OPERATOR_ACCESS_KEY with at least 16 characters')
        if len(settings.session_secret.get_secret_value()) < 32:
            raise RuntimeError('Portal investigation requires SESSION_SECRET with at least 32 characters')
        url = settings.uipath_webhook_url.get_secret_value().strip()
        parsed = urlparse(url)
        if parsed.scheme not in ({'https'} if settings.app_env == 'production' else {'http', 'https'}) or not parsed.netloc:
            raise RuntimeError('Portal investigation requires a valid UiPath webhook URL')
        header = settings.uipath_webhook_auth_header_name.strip()
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}", header):
            raise RuntimeError('UIPATH_WEBHOOK_AUTH_HEADER_NAME is invalid')
        if header.lower() in {'host', 'content-length', 'content-type', 'transfer-encoding'}:
            raise RuntimeError('UIPATH_WEBHOOK_AUTH_HEADER_NAME is reserved')
        if len(settings.uipath_webhook_auth_header_value.get_secret_value()) < 16:
            raise RuntimeError('Portal investigation requires a webhook authentication value')


@contextmanager
def runtime_storage(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    for name in ('documents', 'staging', 'tmp'):
        private_path(settings, name).mkdir(parents=True, exist_ok=True)
    temporary_dir = str(private_path(settings, 'tmp'))
    # Also tests actual write permission; do not rely on os.access under root.
    with tempfile.TemporaryFile(dir=temporary_dir) as probe:
        probe.write(b'TransferIQ storage probe')
        probe.flush()
        os.fsync(probe.fileno())
    previous = tempfile.tempdir
    tempfile.tempdir = temporary_dir  # Starlette multipart spooled files use this directory.
    try:
        yield
    finally:
        tempfile.tempdir = previous
