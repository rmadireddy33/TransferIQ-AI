"""Current bootstrap plus ordered, additive schema migrations.

Never use create_all to pretend existing tables have been migrated.
"""
from sqlalchemy import inspect

from backend.models.entities import Base
from backend.models import reconciliation  # register version 2 tables
from backend.models import documents  # register version 3 tables
from backend.models import resolution  # register version 4 tables
from backend.services.lifecycle import TRANSITIONS

SCHEMA_VERSION = 4
V4_TABLES = {'resolution_plans', 'review_decisions', 'demo_dispositions'}
V3_TABLES = {"transfer_documents"}
V2_TABLES = {"corporate_actions", "security_identifier_mappings", "cost_basis_records",
             "reconciliation_runs", "transfer_exceptions"}


def migrate_v1_to_v2(connection):
    existing = set(inspect(connection).get_table_names())
    if not (set(Base.metadata.tables) - V2_TABLES - V3_TABLES - V4_TABLES).issubset(existing) or existing & (V2_TABLES | V3_TABLES | V4_TABLES):
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
    if not (set(Base.metadata.tables) - V3_TABLES - V4_TABLES).issubset(tables) or tables & (V3_TABLES | V4_TABLES):
        raise RuntimeError("Unexpected version 2 schema; explicit migration review required")
    Base.metadata.tables["transfer_documents"].create(connection)
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Foreign key validation failed during migration")
    connection.exec_driver_sql("PRAGMA user_version=3")


def protect_resolution(connection):
    for table in ('review_decisions', 'demo_dispositions'):
        for action in ('UPDATE', 'DELETE'):
            connection.exec_driver_sql(f"CREATE TRIGGER {table}_deny_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Disposition history is immutable'); END")
        # A replacement can conflict on any UNIQUE key, not just the primary key.
        key = 'decision_id' if table == 'review_decisions' else 'disposition_id'
        match = f'{key}=NEW.{key} OR plan_id=NEW.plan_id'
        if table == 'demo_dispositions':
            match = f'{key}=NEW.{key} OR (plan_id=NEW.plan_id AND exception_id=NEW.exception_id)'
        else:
            match += ' OR review_event_reference=NEW.review_event_reference'
        connection.exec_driver_sql(f"CREATE TRIGGER {table}_deny_replace BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {match}) BEGIN SELECT RAISE(ABORT, 'Disposition history is immutable'); END")
    columns = ('transfer_id','reconciliation_run_id','agent_investigation_id','plan_version','plan_hash','proposed_actions','evidence_references','context','request_key','request_hash','created_at')
    changed = ' OR '.join(f'OLD.{c} IS NOT NEW.{c}' for c in columns)
    connection.exec_driver_sql(f"CREATE TRIGGER resolution_plan_immutable BEFORE UPDATE ON resolution_plans WHEN {changed} BEGIN SELECT RAISE(ABORT, 'Plan content is immutable'); END")
    connection.exec_driver_sql("CREATE TRIGGER resolution_plan_no_replace BEFORE INSERT ON resolution_plans WHEN EXISTS(SELECT 1 FROM resolution_plans WHERE plan_id=NEW.plan_id OR request_key=NEW.request_key) BEGIN SELECT RAISE(ABORT, 'Plan content is immutable'); END")
    connection.exec_driver_sql("CREATE TRIGGER resolution_plan_no_delete BEFORE DELETE ON resolution_plans BEGIN SELECT RAISE(ABORT, 'Plan history is immutable'); END")
    connection.exec_driver_sql("CREATE TRIGGER resolution_plan_transition BEFORE UPDATE OF status ON resolution_plans WHEN OLD.status != NEW.status AND NOT ((OLD.status='PREVIEWED' AND NEW.status='DECIDED') OR (OLD.status='DECIDED' AND NEW.status IN ('EXECUTED','REJECTED'))) BEGIN SELECT RAISE(ABORT, 'Invalid plan transition'); END")


def migrate_v3_to_v4(connection):
    tables = set(inspect(connection).get_table_names())
    if not (set(Base.metadata.tables) - V4_TABLES).issubset(tables) or tables & V4_TABLES:
        raise RuntimeError('Unexpected version 3 schema; explicit migration review required')
    for name, type_ in (('plan_id','VARCHAR(64)'),('event_data','JSON'),('correlation_id','VARCHAR(128)')):
        connection.exec_driver_sql(f'ALTER TABLE audit_events ADD COLUMN {name} {type_}')
    for table in Base.metadata.sorted_tables:
        if table.name in V4_TABLES:
            table.create(connection)
    protect_resolution(connection)
    if connection.exec_driver_sql('PRAGMA foreign_key_check').fetchall():
        raise RuntimeError('Foreign key validation failed during migration')
    connection.exec_driver_sql('PRAGMA user_version=4')


def initialize_database(engine):
    with engine.begin() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
        tables = set(inspect(connection).get_table_names())
        if version == 1:
            migrate_v1_to_v2(connection)
            version = 2
        if version == 2:
            migrate_v2_to_v3(connection)
            version = 3
        if version == 3:
            migrate_v3_to_v4(connection)
            return
        if version == SCHEMA_VERSION:
            if not set(Base.metadata.tables).issubset(tables):
                raise RuntimeError("Incomplete schema; restore or migrate the database explicitly")
            return
        if version != 0 or tables:
            raise RuntimeError(f"Unsupported database schema version {version}; explicit migration required")
        Base.metadata.create_all(connection)
        protect_resolution(connection)
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
