import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.database.migrations import initialize_database, V2_TABLES, V3_TABLES, V4_TABLES, SCHEMA_VERSION
from backend.database.seed import seed_demo
from backend.database.session import create_database_engine, session_factory
from backend.models.entities import Base


def remove_v4(connection):
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in V4_TABLES:
            table.drop(connection)
    for column in ('plan_id','event_data','correlation_id'):
        connection.exec_driver_sql(f'ALTER TABLE audit_events DROP COLUMN {column}')


def make_legacy_database(settings):
    """Recreate the actual v1 table/column layout in an isolated temporary DB."""
    engine = create_database_engine(settings)
    initialize_database(engine)
    seed_demo(session_factory(engine))
    with engine.begin() as connection:
        remove_v4(connection)
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in V2_TABLES | V3_TABLES:
                table.drop(connection)
        connection.exec_driver_sql("ALTER TABLE position_snapshots DROP COLUMN observed_identifier")
        connection.exec_driver_sql("ALTER TABLE receiving_transfer_staging_positions DROP COLUMN snapshot_date")
        connection.exec_driver_sql("ALTER TABLE receiving_transfer_staging_positions DROP COLUMN observed_identifier")
        connection.exec_driver_sql("PRAGMA user_version=1")
    return engine


def test_populated_v3_additive_review_migration(settings):
    engine=create_database_engine(settings)
    initialize_database(engine)
    seed_demo(session_factory(engine))
    with engine.begin() as connection:
        remove_v4(connection)
        connection.exec_driver_sql('PRAGMA user_version=3')
        tables=set(inspect(connection).get_table_names())
        before={table:connection.exec_driver_sql(f'SELECT * FROM {table}').fetchall() for table in tables}
    initialize_database(engine)
    initialize_database(engine)
    with engine.connect() as connection:
        for table,rows in before.items():
            actual=connection.exec_driver_sql(f'SELECT * FROM {table}').fetchall()
            if table=='audit_events':actual=[tuple(r[:-3]) for r in actual]
            assert actual==rows
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall()==[]
        assert connection.exec_driver_sql('PRAGMA user_version').scalar_one()==4
    engine.dispose()


def test_migrate_populated_v1_without_overwrite(settings):
    engine = make_legacy_database(settings)
    try:
        with engine.connect() as connection:
            old_columns = [c["name"] for c in inspect(connection).get_columns("position_snapshots")]
            original = connection.exec_driver_sql("SELECT * FROM position_snapshots ORDER BY position_id").fetchall()
            staging_columns = [c["name"] for c in inspect(connection).get_columns("receiving_transfer_staging_positions")]
            staging = connection.exec_driver_sql("SELECT * FROM receiving_transfer_staging_positions ORDER BY staging_position_id").fetchall()
        initialize_database(engine)
        initialize_database(engine)  # Migration is safe to repeat.
        with engine.begin() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar() == SCHEMA_VERSION
            assert connection.exec_driver_sql(f"SELECT {','.join(old_columns)} FROM position_snapshots ORDER BY position_id").fetchall() == original
            assert connection.exec_driver_sql(f"SELECT {','.join(staging_columns)} FROM receiving_transfer_staging_positions ORDER BY staging_position_id").fetchall() == staging
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM receiving_transfer_staging_positions WHERE snapshot_date IS NULL").scalar() == 7
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
            with pytest.raises(IntegrityError, match="immutable"):
                connection.exec_driver_sql("UPDATE position_snapshots SET quantity='1'")
    finally:
        engine.dispose()


def test_failed_migration_rolls_back_added_columns(settings):
    engine = make_legacy_database(settings)
    try:
        # Simulate a partially customized v1 schema which conflicts with the migration.
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE receiving_transfer_staging_positions ADD COLUMN snapshot_date DATE")
        with pytest.raises(OperationalError):
            initialize_database(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar() == 1
            assert "observed_identifier" not in {c["name"] for c in inspect(connection).get_columns("position_snapshots")}
            assert not V2_TABLES.intersection(inspect(connection).get_table_names())
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM position_snapshots").scalar() == 7
    finally:
        engine.dispose()


def test_v2_to_v3_adds_documents_without_modifying_records(settings):
    engine = create_database_engine(settings)
    try:
        initialize_database(engine)
        seed_demo(session_factory(engine), include_scenarios=True)
        with engine.begin() as connection:
            remove_v4(connection)
            Base.metadata.tables["transfer_documents"].drop(connection)
            connection.exec_driver_sql("PRAGMA user_version=2")
            before = connection.exec_driver_sql("SELECT * FROM position_snapshots ORDER BY position_id").fetchall()
            transfers = connection.exec_driver_sql("SELECT * FROM transfers ORDER BY transfer_id").fetchall()
        initialize_database(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar() == SCHEMA_VERSION
            assert connection.exec_driver_sql("SELECT * FROM position_snapshots ORDER BY position_id").fetchall() == before
            assert connection.exec_driver_sql("SELECT * FROM transfers ORDER BY transfer_id").fetchall() == transfers
            assert connection.exec_driver_sql("SELECT COUNT(*) FROM transfer_documents").scalar() == 0
    finally:
        engine.dispose()
