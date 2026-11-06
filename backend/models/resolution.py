"""Demo disposition ledger. No custody/staging or reconciliation mutations."""
from datetime import datetime
from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.entities import Base
from backend.models.types import UTCDateTime, utcnow


class ResolutionPlan(Base):
    __tablename__ = 'resolution_plans'
    __table_args__ = (UniqueConstraint('request_key'), CheckConstraint('plan_version >= 1'),
        CheckConstraint("status IN ('PREVIEWED','DECIDED','EXECUTED','REJECTED')"))
    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey('transfers.transfer_id'))
    reconciliation_run_id: Mapped[str] = mapped_column(ForeignKey('reconciliation_runs.reconciliation_run_id'))
    agent_investigation_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default='PREVIEWED')
    plan_version: Mapped[int] = mapped_column(Integer, default=1)
    plan_hash: Mapped[str] = mapped_column(String(64))
    proposed_actions: Mapped[list] = mapped_column(JSON)
    evidence_references: Mapped[list] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON)
    request_key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ReviewDecision(Base):
    __tablename__ = 'review_decisions'
    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey('resolution_plans.plan_id'), unique=True)
    review_outcome: Mapped[str] = mapped_column(String(32))
    reviewer_reference: Mapped[str] = mapped_column(String(256))
    reviewer_comments: Mapped[str] = mapped_column(String(2000))
    additional_information: Mapped[str] = mapped_column(String(2000))
    review_event_reference: Mapped[str] = mapped_column(String(256), unique=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    decided_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class DemoDisposition(Base):
    __tablename__ = 'demo_dispositions'
    __table_args__ = (UniqueConstraint('plan_id', 'exception_id'),)
    disposition_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey('resolution_plans.plan_id'))
    exception_id: Mapped[str] = mapped_column(ForeignKey('transfer_exceptions.exception_id'))
    action: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
