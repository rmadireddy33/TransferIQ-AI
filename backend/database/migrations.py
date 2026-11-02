"""Current bootstrap plus ordered, additive schema migrations.

Never use create_all to pretend existing tables have been migrated.
"""
from sqlalchemy import inspect

from backend.models.entities import Base
from backend.models import reconciliation  # register version 2 tables
from backend.models import documents  # register version 3 tables
from backend.services.lifecycle import TRANSITIONS

SCHEMA_VERSION = 3
V3_TABLES = {"transfer_documents"}
V2_TABLES = {"corporate_actions", "security_identifier_mappings", "cost_basis_records",
             "reconciliation_runs", "transfer_exceptions"}


def migrate_v1_to_v2(connection):
    existing = set(inspect(connection).get_table_names())
    if not (set(Base.metadata.tables) - V2_TABLES - V3_TABLES).issubset(existing) or existing & (V2_TABLES | V3_TABLES):
        raise RuntimeError("Unexpected version 1 schema; explicit migration review required")
    # Nullable columns preserve every existing value; no invented snapshot dates.
    connection.exec_driver_sql("ALTER TABLE position_snapshots ADD COLUMN observed_identifier VARCHAR(64)")
    connection.exec_driver_sql("ALTER TABLE receiving_transfer_staging_positions ADD COLUMN snapshot_date DATE")
    connection.exec_driver_sql("ALTER TABLE receiving_transfer_staging_positions ADD COLUMN observed_identifier VARCHAR(64)")
    for table in Base.metadata.sorted_tables:
        if table.name in V2_TABLES:
            table.create(connection)
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Foreign key validation failed during migration")
    connection.exec_driver_sql("PRAGMA user_version=2")


def migrate_v2_to_v3(connection):
    tables = set(inspect(connection).get_table_names())
    if not (set(Base.metadata.tables) - V3_TABLES).issubset(tables) or tables & V3_TABLES:
        raise RuntimeError("Unexpected version 2 schema; explicit migration review required")
    Base.metadata.tables["transfer_documents"].create(connection)
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Foreign key validation failed during migration")
    connection.exec_driver_sql("PRAGMA user_version=3")


def initialize_database(engine):
    with engine.begin() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
        tables = set(inspect(connection).get_table_names())
        if version == 1:
            migrate_v1_to_v2(connection)
            version = 2
        if version == 2:
            migrate_v2_to_v3(connection)
            return
        if version == SCHEMA_VERSION:
            if not set(Base.metadata.tables).issubset(tables):
                raise RuntimeError("Incomplete schema; restore or migrate the database explicitly")
            return
        if version != 0 or tables:
            raise RuntimeError(f"Unsupported database schema version {version}; explicit migration required")
        Base.metadata.create_all(connection)
        for table in ("position_snapshots", "audit_events"):
            primary_key = "position_id" if table == "position_snapshots" else "event_id"
            match = f"{primary_key} = NEW.{primary_key}"
            if table == "position_snapshots":
                match += (" OR (account_id = NEW.account_id AND security_id = NEW.security_id"
                          " AND snapshot_date = NEW.snapshot_date AND source_system = NEW.source_system)")
            # REPLACE may delete without firing DELETE triggers in SQLite. Deny
            # replacement by primary key AND by the snapshot's natural unique key.
            connection.exec_driver_sql(f"""
                CREATE TRIGGER {table}_deny_replace BEFORE INSERT ON {table}
                WHEN EXISTS (SELECT 1 FROM {table} WHERE {match})
                BEGIN SELECT RAISE(ABORT, '{table} are immutable'); END
            """)
            for action in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(f"""
                    CREATE TRIGGER {table}_deny_{action.lower()}
                    BEFORE {action} ON {table}
                    BEGIN SELECT RAISE(ABORT, '{table} are immutable'); END
                """)
        allowed = " OR ".join(
            f"(OLD.status = '{source.value}' AND NEW.status = '{target.value}')"
            for source, targets in TRANSITIONS.items() for target in sorted(targets)
        )
        connection.exec_driver_sql(f"""
            CREATE TRIGGER transfers_validate_transition BEFORE UPDATE OF status ON transfers
            WHEN OLD.status != NEW.status AND NOT ({allowed})
            BEGIN SELECT RAISE(ABORT, 'Invalid transfer status transition'); END
        """)
        connection.exec_driver_sql("""
            CREATE TRIGGER transfers_initial_state BEFORE INSERT ON transfers
            WHEN NEW.status != 'DRAFT'
            BEGIN SELECT RAISE(ABORT, 'Transfers must start in DRAFT'); END
        """)
        connection.exec_driver_sql(f"PRAGMA user_version={SCHEMA_VERSION}")
