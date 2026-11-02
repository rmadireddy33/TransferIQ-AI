import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from backend.api.dependencies import fail
from backend.models.entities import AuditEvent, PositionSnapshot, ReceivingTransferStagingPosition, Security, Transfer, TransferType
from backend.models.reconciliation import CorporateAction, CostBasisRecord, ReconciliationRun, SecurityIdentifierMapping, TransferException
from backend.models.types import utcnow
from backend.services.reconciliation_rules import RULE_VERSION, evaluate
from backend.services.transfers import require_record


def serialize_value(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def snapshot(row):
    return {c.key: serialize_value(getattr(row, c.key)) for c in row.__table__.columns}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def collect_inputs(session, transfer, source_date=None):
    if transfer.transfer_type != TransferType.FULL:
        fail(422, "unsupported_partial_scope", "Partial transfer reconciliation requires an explicit asset scope, not yet supported")
    selected_date = source_date or session.scalar(select(func.max(PositionSnapshot.snapshot_date)).where(
        PositionSnapshot.account_id == transfer.source_account_id))
    source = session.scalars(select(PositionSnapshot).where(PositionSnapshot.account_id == transfer.source_account_id,
        PositionSnapshot.snapshot_date == selected_date).order_by(PositionSnapshot.position_id)).all()
    if not source:
        fail(422, "source_snapshot_missing", "No source snapshot exists for the selected date/account")
    target = session.scalars(select(ReceivingTransferStagingPosition).where(
        ReceivingTransferStagingPosition.transfer_id == transfer.transfer_id).order_by(
        ReceivingTransferStagingPosition.staging_position_id)).all()
    ids = {row.security_id for row in source + target}
    securities = session.scalars(select(Security).where(Security.security_id.in_(ids)).order_by(Security.security_id)).all()
    identifiers = {row.observed_identifier for row in source + target if row.observed_identifier}
    identifiers.update(s.canonical_identifier for s in securities)
    mappings = session.scalars(select(SecurityIdentifierMapping).where(
        (SecurityIdentifierMapping.canonical_security_id.in_(ids)) |
        (SecurityIdentifierMapping.old_identifier.in_(identifiers)) |
        (SecurityIdentifierMapping.new_identifier.in_(identifiers))).order_by(SecurityIdentifierMapping.mapping_id)).all()
    actions = session.scalars(select(CorporateAction).where(CorporateAction.security_id.in_(ids)).order_by(
        CorporateAction.corporate_action_id)).all()
    basis = session.scalars(select(CostBasisRecord).where(CostBasisRecord.transfer_id == transfer.transfer_id).order_by(
        CostBasisRecord.cost_basis_id)).all()
    return dict(rule_version=RULE_VERSION, transfer=snapshot(transfer), source_date=str(selected_date),
                source=[snapshot(row) for row in source], target=[snapshot(row) for row in target],
                securities=[snapshot(row) for row in securities], mappings=[snapshot(row) for row in mappings],
                actions=[snapshot(row) for row in actions], cost_basis=[snapshot(row) for row in basis])


def latest_run(session, transfer_id):
    require_record(session, Transfer, transfer_id)
    run = session.scalar(select(ReconciliationRun).where(ReconciliationRun.transfer_id == transfer_id)
                         .order_by(ReconciliationRun.last_requested_at.desc(), ReconciliationRun.reconciliation_run_id.desc()).limit(1))
    if not run:
        fail(404, "reconciliation_not_found", "No completed reconciliation exists for this transfer")
    return run


def reconcile(session, transfer_id, source_date=None):
    with session.begin():
        transfer = require_record(session, Transfer, transfer_id)
        inputs = collect_inputs(session, transfer, source_date)
        digest = fingerprint(inputs)
        existing = session.scalar(select(ReconciliationRun).where(
            ReconciliationRun.transfer_id == transfer_id, ReconciliationRun.input_fingerprint == digest))
        if existing:
            existing.last_requested_at = utcnow()
            return existing, False
        started = utcnow()
        result = evaluate(inputs)
        exceptions = result.pop("exceptions")
        run = ReconciliationRun(reconciliation_run_id=f"REC-{uuid4()}", transfer_id=transfer_id,
            input_fingerprint=digest, source_snapshot_version=fingerprint(inputs["source"]),
            target_snapshot_version=fingerprint(inputs["target"]), input_data=inputs,
            started_at=started, completed_at=utcnow(), last_requested_at=utcnow(), **result)
        session.add(run)
        session.flush()
        for item in exceptions:
            session.add(TransferException(exception_id=f"EXC-{uuid4()}", reconciliation_run_id=run.reconciliation_run_id,
                                          transfer_id=transfer_id, **item))
        session.add(AuditEvent(event_id=str(uuid4()), transfer_id=transfer_id, actor="api-service",
            action="RECONCILIATION_COMPLETED", previous_status=transfer.status.value, new_status=transfer.status.value))
        # Results are separate from the business lifecycle. Never mutate a position
        # or skip approval/lifecycle transitions because a comparison completed.
    return run, True
