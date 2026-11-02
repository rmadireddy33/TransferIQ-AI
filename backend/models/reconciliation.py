"""Persisted reference evidence and reconciliation history; never custody corrections."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.entities import Base
from backend.models.types import ExactQuantity, UTCDateTime, utcnow


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = (CheckConstraint("numerator > 0 AND numerator <= 1000000000"),
                     CheckConstraint("denominator > 0 AND denominator <= 1000000000"))
    corporate_action_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32))
    numerator: Mapped[int] = mapped_column(Integer)
    denominator: Mapped[int] = mapped_column(Integer)
    effective_date: Mapped[date] = mapped_column(Date, index=True)
    verified: Mapped[bool] = mapped_column(Boolean(create_constraint=True), default=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SecurityIdentifierMapping(Base):
    __tablename__ = "security_identifier_mappings"
    __table_args__ = (CheckConstraint("old_identifier != new_identifier"),)
    mapping_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    old_identifier: Mapped[str] = mapped_column(String(64), index=True)
    new_identifier: Mapped[str] = mapped_column(String(64), index=True)
    canonical_security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    effective_date: Mapped[date] = mapped_column(Date)
    verified: Mapped[bool] = mapped_column(Boolean(create_constraint=True), default=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(256))


class CostBasisRecord(Base):
    __tablename__ = "cost_basis_records"
    cost_basis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("transfers.transfer_id"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    quantity: Mapped[Decimal | None] = mapped_column(ExactQuantity())
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    cost_basis_amount: Mapped[Decimal | None] = mapped_column(ExactQuantity())
    status: Mapped[str] = mapped_column(String(32), default="INCOMPLETE")
    evidence_reference: Mapped[str | None] = mapped_column(String(256))


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    __table_args__ = (
        UniqueConstraint("transfer_id", "input_fingerprint"),
        UniqueConstraint("reconciliation_run_id", "transfer_id"),
        CheckConstraint("execution_status = 'COMPLETED'"),
        CheckConstraint("total_positions = directly_matched + evidence_explained + unresolved_count"),
        CheckConstraint("directly_matched >= 0 AND evidence_explained >= 0 AND unresolved_count >= 0 AND cost_basis_issues >= 0"),
    )
    reconciliation_run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("transfers.transfer_id"), index=True)
    source_snapshot_version: Mapped[str] = mapped_column(String(64))
    target_snapshot_version: Mapped[str] = mapped_column(String(64))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    execution_status: Mapped[str] = mapped_column(String(32), default="COMPLETED")
    status: Mapped[str] = mapped_column(String(32))
    total_positions: Mapped[int] = mapped_column(Integer)
    directly_matched: Mapped[int] = mapped_column(Integer)
    evidence_explained: Mapped[int] = mapped_column(Integer)
    unresolved_count: Mapped[int] = mapped_column(Integer)
    cost_basis_issues: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    # Last requested time is metadata, not part of immutable calculation results.
    last_requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    input_data: Mapped[dict] = mapped_column(JSON)
    position_results: Mapped[list] = mapped_column(JSON)


class TransferException(Base):
    __tablename__ = "transfer_exceptions"
    __table_args__ = (
        ForeignKeyConstraint(["reconciliation_run_id", "transfer_id"],
                             ["reconciliation_runs.reconciliation_run_id", "reconciliation_runs.transfer_id"]),
        UniqueConstraint("reconciliation_run_id", "security_id", "exception_type"),
        CheckConstraint("resolution_status IN ('EXPLAINED', 'UNRESOLVED', 'REQUIRES_INVESTIGATION')"),
    )
    exception_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reconciliation_run_id: Mapped[str] = mapped_column(String(64), index=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("transfers.transfer_id"), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.security_id"), index=True)
    exception_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(16))
    source_quantity: Mapped[Decimal | None] = mapped_column(ExactQuantity())
    target_quantity: Mapped[Decimal | None] = mapped_column(ExactQuantity())
    expected_quantity: Mapped[Decimal | None] = mapped_column(ExactQuantity())
    # Signed Decimal string, unlike the nonnegative quantity storage type.
    difference: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(2000))
    evidence_references: Mapped[list] = mapped_column(JSON)
    resolution_status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
