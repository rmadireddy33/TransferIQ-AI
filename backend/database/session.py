from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.core.config import Settings


def create_database_engine(settings: Settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(settings.database_path)),
        connect_args={"check_same_thread": False, "timeout": settings.sqlite_busy_timeout_ms / 1000},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, record):
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
        cursor.execute("PRAGMA journal_mode=WAL")
        if cursor.fetchone()[0].lower() != "wal":
            raise RuntimeError("SQLite WAL could not be enabled")
        cursor.execute("PRAGMA synchronous=FULL")
        # SQLite's own temporary sorts must not spill into ephemeral OS storage.
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

    @event.listens_for(engine, "begin")
    def explicit_begin(connection):
        # Transactional DDL and consistent reads, including on Python's legacy sqlite driver.
        connection.exec_driver_sql("BEGIN")

    return engine


def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
