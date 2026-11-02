"""Idempotent fictional seed. CLI-explicit, or opt-in startup with SEED_DEMO_DATA=1."""
from datetime import date, datetime, timezone
from decimal import Decimal

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.session import create_database_engine, session_factory
from backend.models.entities import (AuditEvent, BrokerageAccount, BrokerageFirm, Client,
    FirmType, PositionSnapshot, ReceivingTransferStagingPosition, Security, Transfer,
    TransferStatus, TransferType)

SEED_TIME = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
SECURITIES = [
    ("DEMOALP", "Fictional Alpine Lantern", "100.125"),
    ("DEMOBRK", "Fictional Brookhaven Robotics", "75"),
    ("DEMOCED", "Fictional Cedar Orbit", "42.5"),
    ("DEMODUN", "Fictional Dune Harbor", "200"),
    ("DEMOELM", "Fictional Elm Cascade", "18.00000001"),
    ("DEMOFER", "Fictional Fern Compass", "310.75"),
    ("DEMOGLE", "Fictional Glen Prism", "64"),
]


def seed_demo(factory, include_scenarios=False) -> int:
    inserted = 0
    with factory.begin() as session:
        def add(model, identifier, **fields):
            nonlocal inserted
            if session.get(model, identifier) is None:
                primary_key = next(iter(model.__table__.primary_key)).key
                session.add(model(**{primary_key: identifier}, **fields))
                session.flush()
                inserted += 1
                return True
            return False

        add(BrokerageFirm, "FIRM-SUMMIT", firm_name="Summit Wealth", firm_type=FirmType.DELIVERING, created_at=SEED_TIME)
        add(BrokerageFirm, "FIRM-NORTHSTAR", firm_name="Northstar Securities", firm_type=FirmType.RECEIVING, created_at=SEED_TIME)
        for number, first, last in [(1, "Avery", "DemoVale"), (2, "Morgan", "DemoReed")]:
            client_id = f"CLI-{number:03}"
            add(Client, client_id, first_name=first, last_name=last,
                email=f"fictional.client{number}@example.invalid", status="ACTIVE", created_at=SEED_TIME)
            for role, firm in [("SRC", "FIRM-SUMMIT"), ("DST", "FIRM-NORTHSTAR")]:
                add(BrokerageAccount, f"ACC-{role}-{number:03}", client_id=client_id, firm_id=firm,
                    account_number=f"FICTIONAL-{role}-{number:03}", account_type="INDIVIDUAL_DEMO",
                    status="ACTIVE", created_at=SEED_TIME)
        created_transfer = add(Transfer, "TRF-1001", client_id="CLI-001", delivering_firm_id="FIRM-SUMMIT",
            receiving_firm_id="FIRM-NORTHSTAR", source_account_id="ACC-SRC-001", destination_account_id="ACC-DST-001",
            transfer_type=TransferType.FULL, simulated_acats_control_number="SIM-DEMO-1001",
            status=TransferStatus.DRAFT, created_at=SEED_TIME, updated_at=SEED_TIME)
        if created_transfer:
            add(AuditEvent, "AUD-SEED-1001", transfer_id="TRF-1001", actor="fictional-demo-seeder",
                action="DEMO_TRANSFER_CREATED", new_status="DRAFT", created_at=SEED_TIME)
        for number, (symbol, name, quantity) in enumerate(SECURITIES, start=1):
            security_id = f"SEC-{number:03}"
            add(Security, security_id, symbol=symbol, security_name=name, security_type="FICTIONAL_EQUITY",
                canonical_identifier=f"FICTIONAL-SECURITY-{number:03}", status="ACTIVE")
            add(PositionSnapshot, f"POS-{number:03}", account_id="ACC-SRC-001", security_id=security_id,
                quantity=Decimal(quantity), snapshot_date=date(2026, 1, 15),
                source_system="FICTIONAL_DELIVERING_DEMO", created_at=SEED_TIME)
            add(ReceivingTransferStagingPosition, f"STG-{number:03}", transfer_id="TRF-1001",
                security_id=security_id, quantity=Decimal(quantity), status="STAGED", version=1,
                created_at=SEED_TIME, updated_at=SEED_TIME)
    if include_scenarios:
        from backend.database.seed_reconciliation import seed_scenarios
        inserted += seed_scenarios(factory)
    return inserted


def main():
    settings = Settings.from_environment()
    engine = create_database_engine(settings)
    try:
        initialize_database(engine)
        count = seed_demo(session_factory(engine), include_scenarios=True)
        print(f"Fictional demonstration seed complete: {count} rows inserted; existing records preserved.")
        from backend.database.seed_documents import seed_documents
        document_count, manifest = seed_documents(session_factory(engine), settings)
        print(f"PDF samples ready: {len(manifest)}; new document records: {document_count}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
