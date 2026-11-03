from copy import deepcopy
from datetime import date
from decimal import Decimal, localcontext

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.database.seed import seed_demo
from backend.main import create_app
from backend.models.entities import AuditEvent, PositionSnapshot, ReceivingTransferStagingPosition, Transfer
from backend.models.reconciliation import CorporateAction, CostBasisRecord, ReconciliationRun, SecurityIdentifierMapping, TransferException
from backend.services.reconciliation import collect_inputs, fingerprint
from backend.services.reconciliation_rules import evaluate


@pytest.fixture
def scenario_client(client, app):
    seed_demo(app.state.session_factory, include_scenarios=True)
    return client


def execute(client, auth, tid="TRF-1002", **body):
    response = client.post(f"/api/transfers/{tid}/reconcile", headers=auth, json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


def stored_snapshot(app, table):
    with app.state.engine.connect() as connection:
        return [tuple(row) for row in connection.exec_driver_sql(f"SELECT * FROM {table} ORDER BY 1")]


@pytest.mark.parametrize("tid,total,direct,explained,unresolved,basis", [
    ("TRF-1001", 7, 7, 0, 0, 0), ("TRF-1002", 7, 5, 1, 1, 0),
    ("TRF-1003", 1, 0, 1, 0, 0), ("TRF-1004", 7, 7, 0, 0, 1),
    ("TRF-1005", 1, 0, 0, 1, 0),
])
def test_scenario_results(scenario_client, auth, app, tid, total, direct, explained, unresolved, basis):
    before = stored_snapshot(app, "position_snapshots")
    staging = stored_snapshot(app, "receiving_transfer_staging_positions")
    body = execute(scenario_client, auth, tid)
    assert body["summary"] == dict(totalPositions=total, directlyMatched=direct,
        evidenceExplained=explained, unresolved=unresolved, costBasisIssues=basis)
    assert body["status"] == ("EXCEPTIONS_DETECTED" if unresolved or basis else "RECONCILED")
    assert body["executionStatus"] == "COMPLETED"
    assert stored_snapshot(app, "position_snapshots") == before
    assert stored_snapshot(app, "receiving_transfer_staging_positions") == staging
    assert scenario_client.get(f"/api/transfers/{tid}", headers=auth).json()["status"] == "DRAFT"


def test_split_and_shortage_details(scenario_client, auth):
    result = execute(scenario_client, auth)
    split, shortage = result["exceptions"]
    assert split["securityId"] == "SEC-103"
    assert split["exceptionType"] == "CORPORATE_ACTION_TIMING"
    assert split["status"] == "EXPLAINED" and split["evidenceReferences"] == ["CA-2026-081"]
    assert Decimal(split["normalizedQuantity"]) == 80
    assert Decimal(split["sourceQuantity"]) == 40
    assert Decimal(shortage["expectedQuantity"]) == 120
    assert Decimal(shortage["targetQuantity"]) == 100
    assert Decimal(shortage["difference"]) == -20
    assert shortage["status"] == "UNRESOLVED" and shortage["evidenceReferences"] == []


@pytest.mark.parametrize("effective", [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 16)])
def test_split_outside_comparison_period(scenario_client, auth, app, effective):
    with app.state.session_factory.begin() as session:
        session.get(CorporateAction, "CA-2026-081").effective_date = effective
    body = execute(scenario_client, auth)
    assert body["summary"]["evidenceExplained"] == 0
    assert body["summary"]["unresolved"] == 2


@pytest.mark.parametrize("field,value", [("verified", False), ("evidence_reference", None), ("action_type", "UNSUPPORTED")])
def test_insufficient_split_evidence(scenario_client, auth, app, field, value):
    with app.state.session_factory.begin() as session:
        setattr(session.get(CorporateAction, "CA-2026-081"), field, value)
    body = execute(scenario_client, auth)
    assert body["summary"]["evidenceExplained"] == 0
    assert body["summary"]["unresolved"] == 2
    assert body["exceptions"][0]["expectedQuantity"] is None


@pytest.mark.parametrize("effective,reference", [(date(2026, 8, 10), "ANOTHER"), (date(2026, 8, 11), "CA-2026-081")])
def test_duplicate_action_not_applied_twice(scenario_client, auth, app, effective, reference):
    with app.state.session_factory.begin() as session:
        session.add(CorporateAction(corporate_action_id="DUPLICATE-ACTION", security_id="SEC-103", action_type="SPLIT",
            numerator=2, denominator=1, effective_date=effective, verified=True, evidence_reference=reference))
        session.get(ReceivingTransferStagingPosition, "STG-1002-SEC-103").quantity = Decimal("160")
    result = execute(scenario_client, auth)
    assert result["summary"]["evidenceExplained"] == 0
    assert result["summary"]["unresolved"] == 2
    issue = next(e for e in result["exceptions"] if e["exceptionType"] == "REQUIRES_INVESTIGATION")
    assert "Duplicate" in issue["description"]


def test_distinct_actions_compose_once(scenario_client, auth, app):
    with app.state.session_factory.begin() as session:
        session.add(CorporateAction(corporate_action_id="SECOND-ACTION", security_id="SEC-103", action_type="SPLIT",
            numerator=3, denominator=1, effective_date=date(2026, 8, 11), verified=True, evidence_reference="SECOND-EVIDENCE"))
        session.get(ReceivingTransferStagingPosition, "STG-1002-SEC-103").quantity = Decimal("240")
    result = execute(scenario_client, auth)
    assert result["summary"]["evidenceExplained"] == 1
    assert Decimal(result["exceptions"][0]["normalizedQuantity"]) == 240


@pytest.mark.parametrize("field,value", [("verified", False), ("effective_date", date(2026, 8, 16)),
    ("canonical_security_id", "SEC-103"), ("evidence_reference", None), ("new_identifier", "WRONG")])
def test_invalid_identifier_mapping(scenario_client, auth, app, field, value):
    with app.state.session_factory.begin() as session:
        setattr(session.get(SecurityIdentifierMapping, "MAP-2026-201"), field, value)
    result = execute(scenario_client, auth, "TRF-1003")
    assert result["summary"]["unresolved"] == 1
    assert result["exceptions"][0]["status"] == "REQUIRES_INVESTIGATION"


def test_ambiguous_mapping_rejected(scenario_client, auth, app):
    with app.state.session_factory.begin() as session:
        session.add(SecurityIdentifierMapping(mapping_id="CONFLICT", old_identifier="FICTIONAL-201-OLD",
            new_identifier="OTHER", canonical_security_id="SEC-103", verified=True,
            effective_date=date(2026, 8, 10), evidence_reference="CONFLICT"))
    assert execute(scenario_client, auth, "TRF-1003")["summary"]["unresolved"] == 1


def test_missing_security(scenario_client, auth, app):
    with app.state.session_factory.begin() as session:
        session.delete(session.get(ReceivingTransferStagingPosition, "STG-1002-SEC-101"))
    result = execute(scenario_client, auth)
    assert any(e["exceptionType"] == "MISSING_SECURITY" and e["securityId"] == "SEC-101" for e in result["exceptions"])


def test_extra_security(scenario_client, auth, app):
    with app.state.session_factory.begin() as session:
        session.add(ReceivingTransferStagingPosition(staging_position_id="EXTRA", transfer_id="TRF-1002",
            security_id="SEC-001", quantity=Decimal("1"), snapshot_date=date(2026, 8, 15)))
    result = execute(scenario_client, auth)
    assert result["summary"]["totalPositions"] == 8
    assert any(e["exceptionType"] == "EXTRA_SECURITY" for e in result["exceptions"])


def test_duplicate_input_rows_are_not_aggregated(scenario_client, app):
    with app.state.session_factory() as session:
        data = collect_inputs(session, session.get(Transfer, "TRF-1002"))
    data["target"].append(deepcopy(data["target"][0]))
    result = evaluate(data)
    duplicate = next(e for e in result["exceptions"] if e["exception_type"] == "DUPLICATE_POSITION")
    assert duplicate["target_quantity"] is None
    assert result["unresolved_count"] == 2


def test_database_duplicate_staging_still_rejected(scenario_client, app):
    with app.state.session_factory() as session:
        session.add(ReceivingTransferStagingPosition(staging_position_id="DUP", transfer_id="TRF-1002",
            security_id="SEC-103", quantity=Decimal("80")))
        with pytest.raises(IntegrityError):
            session.flush()


def test_duplicate_source_streams_require_investigation(scenario_client, auth, app):
    with app.state.session_factory.begin() as session:
        row = session.get(PositionSnapshot, "POS-1002-SEC-103")
        session.add(PositionSnapshot(position_id="OTHER-STREAM", account_id=row.account_id, security_id=row.security_id,
            quantity=row.quantity, snapshot_date=row.snapshot_date, source_system="FICTIONAL_OTHER_STREAM"))
    body = execute(scenario_client, auth)
    assert any(e["exceptionType"] == "DUPLICATE_POSITION" for e in body["exceptions"])


def test_basis_issues_separate_from_quantity(scenario_client, auth):
    body = execute(scenario_client, auth, "TRF-1004")
    assert body["summary"]["directlyMatched"] == 7
    assert body["summary"]["unresolved"] == 0
    assert body["summary"]["costBasisIssues"] == 1
    assert body["exceptions"][0]["exceptionType"] == "COST_BASIS_MISSING"


@pytest.mark.parametrize("field,value,kind", [("cost_basis_amount", None, "COST_BASIS_MISSING"),
    ("quantity", Decimal("999"), "COST_BASIS_INCONSISTENT"),
    ("acquisition_date", date(2027, 1, 1), "COST_BASIS_INCONSISTENT")])
def test_inconsistent_basis(scenario_client, auth, app, field, value, kind):
    with app.state.session_factory.begin() as session:
        setattr(session.get(CostBasisRecord, "BASIS-1002-SEC-101"), field, value)
    result = execute(scenario_client, auth)
    assert result["summary"]["costBasisIssues"] == 1
    assert any(e["exceptionType"] == kind for e in result["exceptions"])


def test_repeated_reconciliation_has_one_run_and_exception_set(scenario_client, auth, app):
    first = execute(scenario_client, auth)
    second = execute(scenario_client, auth)
    assert first["reconciliationRunId"] == second["reconciliationRunId"]
    assert first["exceptions"] == second["exceptions"]
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ReconciliationRun)) == 1
        assert session.scalar(select(func.count()).select_from(TransferException)) == 2
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "RECONCILIATION_COMPLETED")) == 1


def test_new_staging_version_preserves_history(scenario_client, auth, app):
    first = execute(scenario_client, auth)
    with app.state.session_factory.begin() as session:
        row = session.get(ReceivingTransferStagingPosition, "STG-1002-SEC-104")
        row.quantity = Decimal("110")
    second = execute(scenario_client, auth)
    assert first["inputFingerprint"] != second["inputFingerprint"]
    assert first["targetSnapshotVersion"] != second["targetSnapshotVersion"]
    assert first["sourceSnapshotVersion"] == second["sourceSnapshotVersion"]
    latest = scenario_client.get("/api/transfers/TRF-1002/exceptions", headers=auth).json()
    assert latest["reconciliationRunId"] == second["reconciliationRunId"]
    assert latest["total"] == 3  # Two position findings plus now-inconsistent basis.
    assert second["summary"]["costBasisIssues"] == 1
    history = scenario_client.get(f"/api/reconciliation-runs/{first['reconciliationRunId']}", headers=auth).json()
    assert history["exceptions"] == first["exceptions"]


def test_evidence_change_invalidates_fingerprint(scenario_client, auth, app):
    first = execute(scenario_client, auth)
    with app.state.session_factory.begin() as session:
        session.get(CorporateAction, "CA-2026-081").verified = False
    second = execute(scenario_client, auth)
    assert first["inputFingerprint"] != second["inputFingerprint"]
    assert second["summary"]["unresolved"] == 2


def test_exact_precision_and_no_implicit_rounding(scenario_client, app):
    with app.state.session_factory() as session:
        inputs = collect_inputs(session, session.get(Transfer, "TRF-1003"))
    inputs["source"][0]["quantity"] = "999999999999999999.12345678"
    inputs["target"][0]["quantity"] = "999999999999999999.12345677"
    with localcontext() as ctx:
        ctx.prec = 6  # engine must establish its own exact calculation context
        result = evaluate(inputs)
    assert result["exceptions"][0]["difference"] == "-0.00000001"


def test_nonterminating_split_is_unresolved(scenario_client, auth, app):
    with app.state.session_factory.begin() as session:
        action = session.get(CorporateAction, "CA-2026-081")
        action.numerator, action.denominator = 1, 3
    body = execute(scenario_client, auth)
    assert body["summary"]["evidenceExplained"] == 0
    assert "precision" in body["exceptions"][0]["description"]


@pytest.mark.parametrize("quantity", [Decimal("40"), Decimal("80")])
def test_missing_target_date_does_not_explain_split(scenario_client, auth, app, quantity):
    with app.state.session_factory.begin() as session:
        row = session.get(ReceivingTransferStagingPosition, "STG-1002-SEC-103")
        row.snapshot_date = None
        row.quantity = quantity
    assert execute(scenario_client, auth)["summary"]["unresolved"] == 2


def test_reverse_comparison_normalizes_once(scenario_client, app):
    with app.state.session_factory() as session:
        inputs = collect_inputs(session, session.get(Transfer, "TRF-1002"))
    source = next(p for p in inputs["source"] if p["security_id"] == "SEC-103")
    target = next(p for p in inputs["target"] if p["security_id"] == "SEC-103")
    source.update(quantity="80", snapshot_date="2026-08-15")
    target.update(quantity="40", snapshot_date="2026-08-01")
    result = evaluate(inputs)
    assert result["evidence_explained"] == 1
    assert next(e for e in result["exceptions"] if e["security_id"] == "SEC-103")["expected_quantity"] == "40"


def test_invalid_transfer(scenario_client, auth):
    assert scenario_client.post("/api/transfers/absent/reconcile", headers=auth).status_code == 404
    assert scenario_client.get("/api/reconciliation-runs/absent", headers=auth).status_code == 404
    assert scenario_client.get("/api/transfers/TRF-1002/reconciliation", headers=auth).status_code == 404


@pytest.mark.parametrize("method,path", [("post", "/api/transfers/TRF-1002/reconcile"),
    ("get", "/api/transfers/TRF-1002/reconciliation"), ("get", "/api/transfers/TRF-1002/exceptions"),
    ("get", "/api/reconciliation-runs/anything"), ("get", "/api/corporate-actions"),
    ("get", "/api/securities/SEC-201/identifier-mappings"), ("get", "/api/securities/SEC-103/corporate-actions")])
def test_new_routes_require_auth(scenario_client, method, path):
    assert getattr(scenario_client, method)(path).status_code == 401


def test_reference_routes_and_schema_validation(scenario_client, auth):
    assert scenario_client.get("/api/corporate-actions", headers=auth).json()["total"] == 1
    assert scenario_client.get("/api/securities/SEC-103/corporate-actions", headers=auth).json()["total"] == 1
    assert scenario_client.get("/api/securities/SEC-201/identifier-mappings", headers=auth).json()["total"] == 1
    assert scenario_client.get("/api/securities/absent/corporate-actions", headers=auth).status_code == 404
    assert scenario_client.post("/api/transfers/TRF-1002/reconcile", headers=auth, json={"sourceSnapshotDate": "invalid"}).status_code == 422
    assert scenario_client.post("/api/transfers/TRF-1002/reconcile", headers=auth, json={"sourceSnapshotDate": "2025-01-01"}).status_code == 422


def test_restart_preserves_reconciliation(settings, auth):
    app = create_app(settings)
    with TestClient(app) as client:
        seed_demo(app.state.session_factory, include_scenarios=True)
        first = execute(client, auth)
    with TestClient(create_app(settings)) as client:
        existing = client.get(f"/api/reconciliation-runs/{first['reconciliationRunId']}", headers=auth).json()
        assert existing == first
        assert execute(client, auth)["reconciliationRunId"] == first["reconciliationRunId"]


def test_extended_seed_is_idempotent(scenario_client, app):
    snapshots = stored_snapshot(app, "position_snapshots")
    assert seed_demo(app.state.session_factory, include_scenarios=True) == 0
    assert stored_snapshot(app, "position_snapshots") == snapshots


def test_transaction_failure_rolls_back_run_and_exceptions(scenario_client, auth, app):
    with app.state.engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TRIGGER test_failure BEFORE INSERT ON transfer_exceptions
            BEGIN SELECT RAISE(ABORT, 'injected persistence failure'); END""")
    assert scenario_client.post("/api/transfers/TRF-1002/reconcile", headers=auth).status_code == 409
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ReconciliationRun)) == 0
        assert session.scalar(select(func.count()).select_from(TransferException)) == 0
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "RECONCILIATION_COMPLETED")) == 0
