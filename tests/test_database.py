from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from backend.core.config import PROJECT_ROOT, Settings
from backend.database.migrations import initialize_database, SCHEMA_VERSION
from backend.database.seed import seed_demo
from backend.database.session import create_database_engine
from backend.main import create_app
from backend.models.entities import (AuditEvent, Base, BrokerageAccount, Client, PositionSnapshot,
    ReceivingTransferStagingPosition, Transfer, TransferStatus)
from backend.services.lifecycle import validate_transition


def test_database_creation_and_pragmas(app, settings):
    assert not settings.database_path.exists()
    with TestClient(app):
        assert settings.database_path.is_file()
        with app.state.engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
            assert connection.exec_driver_sql("PRAGMA temp_store").scalar() == 2
            assert connection.exec_driver_sql("PRAGMA user_version").scalar() == SCHEMA_VERSION
            assert set(Base.metadata.tables).issubset(inspect(connection).get_table_names())


def test_persistence_across_app_restart(settings, transfer_payload):
    first_app = create_app(settings)
    headers = {"X-API-Key": settings.api_key.get_secret_value(), "Idempotency-Key": "persistent-key"}
    with TestClient(first_app) as client:
        seed_demo(first_app.state.session_factory)
        created = client.post("/api/transfers", headers=headers, json=transfer_payload)
        assert created.status_code == 201
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(created.headers["Location"]).json() == created.json()
        assert restarted.get("/api/clients").json()["total"] == 2
        assert restarted.post("/api/transfers", headers=headers, json=transfer_payload).status_code == 200


def test_foreign_keys(client, app):
    with app.state.session_factory.begin() as session:
        session.add(BrokerageAccount(account_id="BAD", client_id="absent", firm_id="FIRM-SUMMIT",
                                    account_number="FICTIONAL-BAD", account_type="DEMO"))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_composite_account_ownership_constraint(client, app):
    with app.state.engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE transfers SET client_id='CLI-002' WHERE transfer_id='TRF-1001'"))


@pytest.mark.parametrize("sql", [
    "UPDATE position_snapshots SET quantity='99' WHERE position_id='POS-001'",
    "DELETE FROM position_snapshots WHERE position_id='POS-001'",
    "UPDATE audit_events SET actor='changed'",
    "DELETE FROM audit_events",
])
def test_immutable_database_records(client, app, sql):
    with app.state.engine.begin() as connection:
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(text(sql))


@pytest.mark.parametrize("delete", [False, True])
def test_immutable_orm_records(client, app, delete):
    with app.state.session_factory() as session:
        position = session.get(PositionSnapshot, "POS-001")
        if delete:
            session.delete(position)
        else:
            position.quantity = Decimal("9")
        with pytest.raises(ValueError, match="immutable"):
            session.flush()
        session.rollback()


@pytest.mark.parametrize("replacement_id", ["POS-001", "REPLACEMENT-ID"])
def test_replace_cannot_bypass_snapshot_immutability(client, app, replacement_id):
    with app.state.engine.begin() as connection:
        with pytest.raises(IntegrityError, match="immutable"):
            connection.execute(text("""INSERT OR REPLACE INTO position_snapshots
                (position_id, account_id, security_id, quantity, snapshot_date, source_system, created_at)
                SELECT :identifier, account_id, security_id, '999', snapshot_date, source_system, created_at
                FROM position_snapshots WHERE position_id='POS-001'"""), {"identifier": replacement_id})
    assert client.get("/api/delivering/accounts/ACC-SRC-001/positions").json()["items"][0]["quantity"] == "100.12500000"


def test_inactive_client_cannot_create(client, app, auth, transfer_payload):
    with app.state.session_factory.begin() as session:
        session.get(Client, "CLI-001").status = "INACTIVE"
    response = client.post("/api/transfers", headers=auth, json=transfer_payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "inactive_record"


def test_exact_decimal_storage(client, app):
    value = Decimal("999999999999999999.12345678")
    with app.state.session_factory.begin() as session:
        session.add(PositionSnapshot(position_id="PRECISION", account_id="ACC-SRC-002", security_id="SEC-001",
            quantity=value, snapshot_date=date(2026, 1, 16), source_system="FICTIONAL_PRECISION_TEST"))
    with app.state.session_factory() as session:
        assert session.get(PositionSnapshot, "PRECISION").quantity == value
        stored = session.execute(text("SELECT quantity, typeof(quantity) FROM position_snapshots WHERE position_id='PRECISION'")).one()
        assert stored == (str(value), "text")


@pytest.mark.parametrize("quantity", [0.1, Decimal("-1"), Decimal("NaN"), Decimal("1e18"), Decimal("0.000000001")])
def test_invalid_quantities(client, app, quantity):
    with app.state.session_factory() as session:
        session.add(PositionSnapshot(position_id="BAD-Q", account_id="ACC-SRC-002", security_id="SEC-001",
            quantity=quantity, snapshot_date=date(2026, 1, 16), source_system="FICTIONAL_BAD_TEST"))
        with pytest.raises(StatementError):
            session.flush()


def test_idempotent_seed_preserves_changes(client, app):
    with app.state.session_factory.begin() as session:
        session.get(Client, "CLI-001").first_name = "ChangedFictionalName"
        session.get(ReceivingTransferStagingPosition, "STG-001").quantity = Decimal("5")
    assert seed_demo(app.state.session_factory) == 0
    assert seed_demo(app.state.session_factory) == 0
    with app.state.session_factory() as session:
        assert session.get(Client, "CLI-001").first_name == "ChangedFictionalName"
        assert session.get(ReceivingTransferStagingPosition, "STG-001").quantity == Decimal("5")
        assert session.scalar(select(func.count()).select_from(PositionSnapshot)) == 7
        assert session.scalar(select(func.count()).select_from(ReceivingTransferStagingPosition)) == 7
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_status_transition_guard(client, app):
    validate_transition(TransferStatus.DRAFT, TransferStatus.SUBMITTED)
    with pytest.raises(ValueError):
        validate_transition(TransferStatus.DRAFT, TransferStatus.COMPLETED)
    with app.state.engine.begin() as connection:
        with pytest.raises(IntegrityError, match="Invalid transfer status transition"):
            connection.execute(text("UPDATE transfers SET status='COMPLETED' WHERE transfer_id='TRF-1001'"))
        connection.execute(text("UPDATE transfers SET status='SUBMITTED' WHERE transfer_id='TRF-1001'"))
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE transfers SET status='BOGUS' WHERE transfer_id='TRF-1001'"))


def test_unique_staging_security(client, app):
    with app.state.session_factory() as session:
        session.add(ReceivingTransferStagingPosition(staging_position_id="DUP", transfer_id="TRF-1001",
                                                     security_id="SEC-001", quantity=Decimal("1")))
        with pytest.raises(IntegrityError):
            session.flush()


def test_transaction_rollback(client, app):
    with pytest.raises(RuntimeError):
        with app.state.session_factory.begin() as session:
            session.get(Client, "CLI-001").first_name = "MustRollback"
            session.flush()
            raise RuntimeError("test interrupted transaction")
    assert client.get("/api/clients/CLI-001").json()["firstName"] == "Avery"


def test_unsupported_schema_not_reset(settings):
    engine = create_database_engine(settings)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA user_version=99")
        with pytest.raises(RuntimeError, match="explicit migration"):
            initialize_database(engine)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA user_version").scalar() == 99
    finally:
        engine.dispose()


def test_unversioned_existing_database_not_adopted(settings):
    engine = create_database_engine(settings)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE existing (id INTEGER)")
        with pytest.raises(RuntimeError, match="explicit migration"):
            initialize_database(engine)
        assert inspect(engine).get_table_names() == ["existing"]
    finally:
        engine.dispose()


def test_configuration_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert Settings().database_path == PROJECT_ROOT / "data" / "transferiq.db"
    assert Settings(data_dir="data").database_path == PROJECT_ROOT / "data" / "transferiq.db"
    assert Settings(data_dir=tmp_path).database_path == tmp_path / "transferiq.db"
    with pytest.raises(ValidationError):
        Settings(data_dir="backend/data")
    with pytest.raises(ValidationError):
        Settings(data_dir="")


def test_invalid_data_directory_fails(tmp_path):
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("keep me")
    with pytest.raises(FileExistsError):
        create_database_engine(Settings(data_dir=file_path))
    assert file_path.read_text() == "keep me"
