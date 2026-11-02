"""Additional fictional scenarios. Insert absent fixture IDs only; never correct existing rows."""
from datetime import date, datetime, timezone
from decimal import Decimal

from backend.models.entities import (AuditEvent, BrokerageAccount, PositionSnapshot,
    ReceivingTransferStagingPosition, Security, Transfer)
from backend.models.reconciliation import CorporateAction, CostBasisRecord, SecurityIdentifierMapping

SOURCE_DATE = date(2026, 8, 1)
TARGET_DATE = date(2026, 8, 15)
STAMP = datetime(2026, 8, 15, 12, tzinfo=timezone.utc)


def seed_scenarios(factory):
    inserted = 0
    with factory.begin() as session:
        def add(model, identifier, **fields):
            nonlocal inserted
            if session.get(model, identifier) is None:
                pk = next(iter(model.__table__.primary_key)).key
                session.add(model(**{pk: identifier}, **fields))
                session.flush()
                inserted += 1
                return True
            return False

        scenarios = {
            1002: [(f"SEC-{101+i}", str(20+i*10), str(20+i*10)) for i in range(7)],
            1003: [("SEC-201", "25", "25")],
            1004: [(f"SEC-{i:03}", str(i*10), str(i*10)) for i in range(1, 8)],
            1005: [("SEC-301", "120", "100")],
        }
        scenarios[1002][2] = ("SEC-103", "40", "80")
        scenarios[1002][3] = ("SEC-104", "120", "100")
        for number, rows in scenarios.items():
            for side, firm in [("SRC", "FIRM-SUMMIT"), ("DST", "FIRM-NORTHSTAR")]:
                add(BrokerageAccount, f"ACC-{side}-{number}", client_id="CLI-002", firm_id=firm,
                    account_number=f"FICTIONAL-{side}-{number}", account_type="INDIVIDUAL_DEMO", created_at=STAMP)
            tid = f"TRF-{number}"
            if add(Transfer, tid, client_id="CLI-002", delivering_firm_id="FIRM-SUMMIT", receiving_firm_id="FIRM-NORTHSTAR",
                   source_account_id=f"ACC-SRC-{number}", destination_account_id=f"ACC-DST-{number}",
                   transfer_type="FULL", status="DRAFT", simulated_acats_control_number=f"SIM-DEMO-{number}",
                   created_at=STAMP, updated_at=STAMP):
                add(AuditEvent, f"AUD-SEED-{number}", transfer_id=tid, actor="fictional-demo-seeder",
                    action="DEMO_TRANSFER_CREATED", new_status="DRAFT", created_at=STAMP)
            for sid, source, target in rows:
                canonical = f"FICTIONAL-{sid}"
                if sid == "SEC-201":
                    canonical = "FICTIONAL-201-NEW"
                add(Security, sid, symbol=f"DEMO{sid.replace('-', '')}", security_name=f"Fictional Scenario Security {sid}",
                    security_type="FICTIONAL_EQUITY", canonical_identifier=canonical)
                # Existing security masters are authoritative; use their actual identifier.
                canonical = session.get(Security, sid).canonical_identifier
                add(PositionSnapshot, f"POS-{number}-{sid}", account_id=f"ACC-SRC-{number}", security_id=sid,
                    quantity=Decimal(source), snapshot_date=SOURCE_DATE, source_system="FICTIONAL_SCENARIO_DEMO",
                    observed_identifier="FICTIONAL-201-OLD" if sid == "SEC-201" else canonical, created_at=STAMP)
                add(ReceivingTransferStagingPosition, f"STG-{number}-{sid}", transfer_id=tid, security_id=sid,
                    quantity=Decimal(target), snapshot_date=TARGET_DATE, observed_identifier=canonical,
                    status="STAGED", version=1, created_at=STAMP, updated_at=STAMP)
                if number != 1004 or sid != "SEC-007":
                    add(CostBasisRecord, f"BASIS-{number}-{sid}", transfer_id=tid, security_id=sid,
                        quantity=Decimal(target), acquisition_date=date(2025, 1, 1), cost_basis_amount=Decimal(target)*10,
                        status="COMPLETE", evidence_reference=f"FICTIONAL-BASIS-{number}-{sid}")
        # Add explicit basis evidence to the original clean demo; do not modify its positions.
        for i, quantity in enumerate(["100.125", "75", "42.5", "200", "18.00000001", "310.75", "64"], 1):
            add(CostBasisRecord, f"BASIS-1001-SEC-{i:03}", transfer_id="TRF-1001", security_id=f"SEC-{i:03}",
                quantity=Decimal(quantity), acquisition_date=date(2025, 1, 1), cost_basis_amount=Decimal(quantity)*10,
                status="COMPLETE", evidence_reference=f"FICTIONAL-BASIS-1001-{i}")
        add(CorporateAction, "CA-2026-081", security_id="SEC-103", action_type="SPLIT", numerator=2, denominator=1,
            effective_date=date(2026, 8, 10), verified=True, evidence_reference="CA-2026-081", created_at=STAMP)
        add(SecurityIdentifierMapping, "MAP-2026-201", old_identifier="FICTIONAL-201-OLD", new_identifier="FICTIONAL-201-NEW",
            canonical_security_id="SEC-201", effective_date=date(2026, 8, 10), verified=True,
            evidence_reference="MAP-2026-201")
    return inserted
