"""Bounded synthetic execution sandboxes, never backed by the private database.

One worker is required. A bounded lock serializes lifecycle/reconciliation work;
each run has its own SQLite database and immutable generated documents.
"""
from contextlib import contextmanager
import hashlib
import re
import shutil
import threading
import time
from uuid import uuid4

from sqlalchemy import Column, Float, MetaData, String, Table, delete, func, inspect, select
from backend.api.dependencies import fail
from backend.database.migrations import initialize_database
from backend.database.seed import seed_demo
from backend.database.seed_documents import seed_missing_documents
from backend.database.session import create_database_engine, session_factory
from backend.services.document_storage import private_path, recover_pending_documents

metadata = MetaData()
runs = Table('demo_runs', metadata,
    Column('run_id', String, primary_key=True), Column('request_hash', String, unique=True, nullable=False),
    Column('transfer_id', String, nullable=False), Column('expires_at', Float, nullable=False))
RUN_PATTERN = re.compile(r'^DEMO-[0-9a-f]{32}$')


class DemoRuns:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.Lock()
        self.root = private_path(settings, 'competition')
        self.root.mkdir(exist_ok=True)
        self.registry_settings = settings.model_copy(update={'data_dir': self.root})
        self.engine = create_database_engine(self.registry_settings)
        with self.engine.begin() as connection:
            version = connection.exec_driver_sql('PRAGMA user_version').scalar_one()
            tables = set(inspect(connection).get_table_names())
            if version == 0 and not tables:
                metadata.create_all(connection)
                connection.exec_driver_sql('PRAGMA user_version=1')
            elif version != 1 or tables != {'demo_runs'}:
                raise RuntimeError('Unsupported demo registry schema; no reset performed')

    @contextmanager
    def locked(self):
        if not self.lock.acquire(timeout=2):
            fail(503, 'demo_busy', 'Demo capacity is busy; retry the same request')
        try:
            yield
        finally:
            self.lock.release()

    def run_settings(self, run_id):
        if not RUN_PATTERN.fullmatch(run_id):
            fail(404, 'not_found', 'Unknown demo run')
        path = private_path(self.settings, f'competition/runs/{run_id}')
        return self.settings.model_copy(update={'data_dir': path})

    def cleanup(self):
        # Only expired, registry-owned synthetic sandboxes. Validate absolute paths
        # before recursive deletion, and never touch DATA_DIR/documents or its DB.
        with self.engine.connect() as connection:
            expired = connection.execute(select(runs).where(runs.c.expires_at <= time.time())).mappings().all()
        for row in expired:
            target = self.run_settings(row['run_id']).data_dir
            parent = (self.root / 'runs').resolve()
            if target.parent != parent or not target.is_relative_to(self.root):
                raise RuntimeError('Unsafe demo cleanup target')
            if target.exists():
                shutil.rmtree(target)
            with self.engine.begin() as connection:
                connection.execute(delete(runs).where(runs.c.run_id == row['run_id']))

    def create(self, transfer_id, request_id):
        digest = hashlib.sha256(request_id.encode()).hexdigest()
        with self.locked():
            self.cleanup()
            with self.engine.connect() as connection:
                row = connection.execute(select(runs).where(runs.c.request_hash == digest)).mappings().first()
                count = connection.scalar(select(func.count()).select_from(runs))
            created = row is None
            if row and row['transfer_id'] != transfer_id:
                fail(409, 'idempotency_conflict', 'Request ID already belongs to a different demo transfer')
            if created:
                if count >= self.settings.demo_max_runs:
                    fail(429, 'demo_quota', 'Demo run capacity reached; retry after existing runs expire')
                used = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
                if used + 5 * 1024 * 1024 > self.settings.demo_storage_limit_mb * 1024 * 1024:
                    fail(429, 'demo_storage_quota', 'Demo storage capacity reached')
                row = dict(run_id='DEMO-' + uuid4().hex, request_hash=digest,
                    transfer_id=transfer_id, expires_at=time.time() + self.settings.demo_run_ttl_hours * 3600)
                with self.engine.begin() as connection:
                    connection.execute(runs.insert().values(**row))
            settings = self.run_settings(row['run_id'])
            engine = create_database_engine(settings)
            try:
                initialize_database(engine)
                factory = session_factory(engine)
                seed_demo(factory, include_scenarios=True)
                recover_pending_documents(factory, settings)
                seed_missing_documents(factory, settings)
            finally:
                engine.dispose()
            return dict(runId=row['run_id'], transferId=transfer_id, expiresAt=row['expires_at'],
                        fictionalDemo=True, evidenceMode='LIVE_SYNTHETIC_BACKEND'), created

    @contextmanager
    def open(self, run_id):
        with self.locked():
            settings = self.run_settings(run_id)
            with self.engine.connect() as connection:
                row = connection.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
            if not row:
                fail(404, 'not_found', 'Unknown demo run')
            if row['expires_at'] <= time.time():
                fail(410, 'demo_expired', 'Demo run expired; start a new run')
            if not settings.database_path.is_file():
                fail(409, 'demo_incomplete', 'Retry run creation with the same request ID')
            engine = create_database_engine(settings)
            try:
                initialize_database(engine)
                with session_factory(engine)() as session:
                    yield row, settings, session
            finally:
                engine.dispose()
