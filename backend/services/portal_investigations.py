"""Persistent, isolated portal-to-Maestro execution tracking.

This registry contains orchestration metadata only. It never stores webhook
credentials and never mutates transfers, positions, exceptions, or plans.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import threading
import time
from uuid import uuid4

from sqlalchemy import Column, Float, JSON, MetaData, String, Table, func, inspect, select, update

from backend.api.dependencies import fail
from backend.database.session import create_database_engine
from backend.services.document_storage import private_path


metadata = MetaData()
investigations = Table(
    "portal_investigations",
    metadata,
    Column("execution_request_id", String(64), primary_key=True),
    Column("operator_id", String(64), nullable=False, index=True),
    Column("transfer_id", String(64), nullable=False, index=True),
    Column("idempotency_hash", String(64), nullable=False, unique=True),
    Column("request_hash", String(64), nullable=False),
    Column("trigger_status", String(32), nullable=False),
    Column("investigation_status", String(32), nullable=False, index=True),
    Column("review_status", String(32), nullable=False),
    Column("workflow_outcome", String(64), nullable=True),
    Column("verification_status", String(64), nullable=True),
    Column("error_summary", String(512), nullable=True),
    Column("audit_reference", String(64), nullable=True),
    Column("run_id", String(64), nullable=True, unique=True),
    Column("plan_id", String(64), nullable=True),
    Column("webhook_event_id", String(128), nullable=True),
    Column("investigation_summary", String(8000), nullable=True),
    Column("evidence_references", JSON, nullable=False),
    Column("proposed_actions", JSON, nullable=False),
    Column("unresolved_exceptions", JSON, nullable=False),
    Column("positions_unchanged", String(8), nullable=True),
    Column("transfer_completed", String(8), nullable=True),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    Column("deadline_at", Float, nullable=False),
)

ACTIVE = {"PENDING", "TRIGGERED", "INVESTIGATING", "AWAITING_HUMAN_REVIEW"}
TERMINAL = {"COMPLETED", "FAILED", "TIMED_OUT"}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iso(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


class PortalInvestigations:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.Lock()
        root = private_path(settings, "portal")
        root.mkdir(exist_ok=True)
        registry_settings = settings.model_copy(update={"data_dir": root})
        self.engine = create_database_engine(registry_settings)
        with self.engine.begin() as connection:
            version = connection.exec_driver_sql("PRAGMA user_version").scalar_one()
            tables = set(inspect(connection).get_table_names())
            if version == 0 and not tables:
                metadata.create_all(connection)
                connection.exec_driver_sql("PRAGMA user_version=2")
            elif version == 1 and tables == {"portal_investigations"}:
                # Step 10C adds only a nullable projection field. Preserve every
                # existing tracking row while upgrading the isolated registry.
                columns = {item["name"] for item in inspect(connection).get_columns("portal_investigations")}
                if "verification_status" not in columns:
                    connection.exec_driver_sql(
                        "ALTER TABLE portal_investigations ADD COLUMN verification_status VARCHAR(64)"
                    )
                connection.exec_driver_sql("PRAGMA user_version=2")
            elif version != 2 or tables != {"portal_investigations"}:
                raise RuntimeError("Unsupported portal investigation registry schema; no reset performed")

    @contextmanager
    def locked(self):
        if not self.lock.acquire(timeout=2):
            fail(503, "portal_busy", "Portal investigation registry is busy")
        try:
            yield
        finally:
            self.lock.release()

    def _expire(self, connection, now: float) -> None:
        connection.execute(update(investigations).where(
            investigations.c.investigation_status.in_(ACTIVE), investigations.c.deadline_at <= now
        ).values(
            investigation_status="TIMED_OUT", review_status="TIMED_OUT",
            error_summary="Workflow did not reach a terminal audited state before the configured deadline.",
            updated_at=now,
        ))

    def create(self, operator_id: str, transfer_id: str, idempotency_key: str):
        now = time.time()
        idempotency_hash = _digest(operator_id + ":" + idempotency_key)
        request_hash = _digest(json.dumps({"transferId": transfer_id}, separators=(",", ":"), sort_keys=True))
        with self.locked(), self.engine.begin() as connection:
            self._expire(connection, now)
            existing = connection.execute(select(investigations).where(
                investigations.c.idempotency_hash == idempotency_hash)).mappings().first()
            if existing:
                if existing["operator_id"] != operator_id or existing["request_hash"] != request_hash:
                    fail(409, "idempotency_conflict", "Idempotency key has different investigation content")
                return dict(existing), False
            recent_user = connection.scalar(select(func.count()).select_from(investigations).where(
                investigations.c.operator_id == operator_id, investigations.c.created_at >= now - 60))
            if recent_user >= self.settings.portal_starts_per_minute:
                fail(429, "portal_rate_limited", "Portal investigation start limit reached")
            user_active = connection.scalar(select(func.count()).select_from(investigations).where(
                investigations.c.operator_id == operator_id,
                investigations.c.investigation_status.in_(ACTIVE)))
            global_active = connection.scalar(select(func.count()).select_from(investigations).where(
                investigations.c.investigation_status.in_(ACTIVE)))
            if user_active >= self.settings.portal_user_max_active:
                fail(409, "investigation_already_active", "This operator already has an active investigation")
            if global_active >= self.settings.portal_global_max_active:
                fail(429, "portal_capacity", "Portal investigation capacity is currently full")
            row = {
                "execution_request_id": "PEX-" + uuid4().hex,
                "operator_id": operator_id,
                "transfer_id": transfer_id,
                "idempotency_hash": idempotency_hash,
                "request_hash": request_hash,
                "trigger_status": "PENDING",
                "investigation_status": "PENDING",
                "review_status": "NOT_STARTED",
                "workflow_outcome": None,
                "verification_status": None,
                "error_summary": None,
                "audit_reference": None,
                "run_id": None,
                "plan_id": None,
                "webhook_event_id": None,
                "investigation_summary": None,
                "evidence_references": [],
                "proposed_actions": [],
                "unresolved_exceptions": [],
                "positions_unchanged": None,
                "transfer_completed": None,
                "created_at": now,
                "updated_at": now,
                "deadline_at": now + self.settings.portal_workflow_timeout_minutes * 60,
            }
            connection.execute(investigations.insert().values(**row))
            return row, True

    def set_trigger_result(self, execution_request_id: str, accepted: bool,
                           event_id: str | None = None, error: str | None = None):
        now = time.time()
        values = {
            "trigger_status": "ACCEPTED" if accepted else "FAILED",
            "investigation_status": "TRIGGERED" if accepted else "FAILED",
            "webhook_event_id": event_id if accepted else None,
            "error_summary": None if accepted else (error or "UiPath did not accept the trigger request."),
            "updated_at": now,
        }
        with self.locked(), self.engine.begin() as connection:
            connection.execute(update(investigations).where(
                investigations.c.execution_request_id == execution_request_id).values(**values))

    def bind_run(self, execution_request_id: str, transfer_id: str, run_id: str):
        with self.locked(), self.engine.begin() as connection:
            row = connection.execute(select(investigations).where(
                investigations.c.execution_request_id == execution_request_id)).mappings().first()
            if not row or row["transfer_id"] != transfer_id or row["investigation_status"] not in {"TRIGGERED", "INVESTIGATING"}:
                fail(404, "portal_investigation_not_found", "Unknown or inactive portal execution request")
            connection.execute(update(investigations).where(
                investigations.c.execution_request_id == execution_request_id).values(
                    run_id=run_id, investigation_status="INVESTIGATING", updated_at=time.time()))

    def update_by_run(self, run_id: str, **values):
        values = {**values, "updated_at": time.time()}
        with self.locked(), self.engine.begin() as connection:
            connection.execute(update(investigations).where(
                investigations.c.run_id == run_id,
                investigations.c.investigation_status.not_in(TERMINAL)).values(**values))

    def read(self, execution_request_id: str, operator_id: str):
        now = time.time()
        with self.locked(), self.engine.begin() as connection:
            self._expire(connection, now)
            row = connection.execute(select(investigations).where(
                investigations.c.execution_request_id == execution_request_id,
                investigations.c.operator_id == operator_id)).mappings().first()
            if not row:
                fail(404, "not_found", "Investigation was not found")
            return self.public(dict(row))

    @staticmethod
    def public(row: dict):
        return {
            "executionRequestId": row["execution_request_id"],
            "transferId": row["transfer_id"],
            "triggerStatus": row["trigger_status"],
            "investigationStatus": row["investigation_status"],
            "reviewStatus": row["review_status"],
            "workflowOutcome": row["workflow_outcome"],
            "verificationStatus": row["verification_status"],
            "startedAt": _iso(row["created_at"]),
            "lastUpdated": _iso(row["updated_at"]),
            "deadlineAt": _iso(row["deadline_at"]),
            "errorSummary": row["error_summary"],
            "auditReference": row["audit_reference"],
            "runId": row["run_id"],
            "planId": row["plan_id"],
            "auditUrl": (
                f"/api/demo/runs/{row['run_id']}/resolution-plans/{row['plan_id']}/audit"
                if row["run_id"] and row["plan_id"] and row["audit_reference"] else None
            ),
            "investigationSummary": row["investigation_summary"],
            "evidenceReferences": row["evidence_references"] or [],
            "proposedActions": row["proposed_actions"] or [],
            "unresolvedExceptions": row["unresolved_exceptions"] or [],
            "positionsUnchanged": None if row["positions_unchanged"] is None else row["positions_unchanged"] == "true",
            "transferCompleted": None if row["transfer_completed"] is None else row["transfer_completed"] == "true",
        }
