"""Volume checks and temporary upload storage, executed at runtime only."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile

from backend.services.document_storage import private_path


def validate_runtime_environment(settings, environ=None):
    env = os.environ if environ is None else environ
    railway = bool(env.get('RAILWAY_ENVIRONMENT_ID'))
    if (railway or settings.app_env == 'production') and not settings.api_key.get_secret_value().strip():
        raise RuntimeError('Production requires API_KEY')
    if railway:
        if settings.app_env != 'production':
            raise RuntimeError('Railway requires APP_ENV=production')
        if env.get('DATA_DIR') != '/data' or settings.data_dir != Path('/data').resolve():
            raise RuntimeError('Railway requires DATA_DIR=/data')
        if env.get('RAILWAY_VOLUME_MOUNT_PATH') != '/data' or not settings.data_dir.is_mount():
            raise RuntimeError('Railway persistent volume must be mounted at /data')


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
