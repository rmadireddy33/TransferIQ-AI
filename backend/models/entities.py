from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (CheckConstraint, Date, Enum, ForeignKey, ForeignKeyConstraint,
                        Integer, JSON, String, UniqueConstraint, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.models.types import ExactQuantity, UTCDateTime, utcnow


class Base(DeclarativeBase):
    pass


class FirmType(StrEnum):
    DELIVERING = "DELIVERING"
    RECEIVING = "RECEIVING"
    BOTH = "BOTH"


class TransferType(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"


class TransferStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    EXCEPTION_DETECTED = "EXCEPTION_DETECTED"
    INVESTIGATING = "INVESTIGATING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"


def enum_column(enum):
    return Enum(enum, native_enum=False, create_constraint=True, validate_strings=True)


class Client(Base):
    __tablename__ = "clients"
    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    accounts: Mapped[list["BrokerageAccount"]] = relationship(back_populates="client")


class BrokerageFirm(Base):
    __tablename__ = "brokerage_firms"
    firm_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    firm_name: Mapped[str] = mapped_column(String(150), unique=True)
    firm_type: Mapped[FirmType] = mapped_column(enum_column(FirmType))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    accounts: Mapped[list["BrokerageAccount"]] = relationship(back_populates="firm")


class BrokerageAccount(Base):
    __tablename__ = "brokerage_accounts"
    __table_args__ = (
        UniqueConstraint("firm_id", "account_number"),
        UniqueConstraint("account_id", "client_id", "firm_id"),
    )
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.client_id"), index=True)
    firm_id: Mapped[str] = mapped_column(ForeignKey("brokerage_firms.firm_id"), index=True)
    account_number: Mapped[str] = mapped_column(String(64))
    account_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    client: Mapped[Client] = relationship(back_populates="accounts")
    firm: Mapped[BrokerageFirm] = relationship(back_populates="accounts")


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        ForeignKeyConstraint(["source_account_id", "client_id", "delivering_firm_id"],
                             ["brokerage_accounts.account_id", "brokerage_accounts.client_id", "brokerage_accounts.firm_id"]),
        ForeignKeyConstraint(["destination_account_id", "client_id", "receiving_firm_id"],
                             ["brokerage_accounts.account_id", "brokerage_accounts.client_id", "brokerage_accounts.firm_id"]),
        CheckConstraint("source_account_id != destination_account_id"),
        CheckConstraint("delivering_firm_id != receiving_firm_id"),
    )
    transfer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.client_id"), index=True)
    delivering_firm_id: Mapped[str] = mapped_column(ForeignKey("brokerage_firms.firm_id"))
    receiving_firm_id: Mapped[str] = mapped_column(ForeignKey("brokerage_firms.firm_id"))
    source_account_id: Mapped[str] = mapped_column(String(64), index=True)
    destination_account_id: Mapped[str] = mapped_column(String(64), index=True)
    transfer_type: Mapped[TransferType] = mapped_column(enum_column(TransferType))
    simulated_acats_control_number: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[TransferStatus] = mapped_column(enum_column(TransferStatus), default=TransferStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    staging_positions: Mapped[list["ReceivingTransferStagingPosition"]] = relationship(back_populates="transfer")


class Security(Base):
    __tablename__ = "securities"
    security_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True)
    security_name: Mapped[str] = mapped_column(String(150))
    security_type: Mapped[str] = mapped_column(String(32))
    canonical_identifier: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"
    __table_args__ = (UniqueConstraint("account_id", "security_id", "snapshot_date", "source_system"),)
    position_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("brokerage_accounts.account_id"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    quantity: Mapped[Decimal] = mapped_column(ExactQuantity())
    snapshot_date: Mapped[date] = mapped_column(Date)
    source_system: Mapped[str] = mapped_column(String(64))
    observed_identifier: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ReceivingTransferStagingPosition(Base):
    __tablename__ = "receiving_transfer_staging_positions"
    __table_args__ = (UniqueConstraint("transfer_id", "security_id"), CheckConstraint("version >= 1"))
    staging_position_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("transfers.transfer_id"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    quantity: Mapped[Decimal] = mapped_column(ExactQuantity())
    status: Mapped[str] = mapped_column(String(32), default="STAGED")
    version: Mapped[int] = mapped_column(Integer, default=1)
    snapshot_date: Mapped[date | None] = mapped_column(Date)
    observed_identifier: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    transfer: Mapped[Transfer] = relationship(back_populates="staging_positions")
    __mapper_args__ = {"version_id_col": version}


class AuditEvent(Base):
    __tablename__ = "audit_events"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("transfers.transfer_id"), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    plan_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    # The only mutation is transfer creation by one service principal in Step 2.
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    transfer_id: Mapped[str] = mapped_column(ForeignKey("transfers.transfer_id"))


@event.listens_for(PositionSnapshot, "before_update")
@event.listens_for(PositionSnapshot, "before_delete")
def deny_snapshot_mutation(mapper, connection, target):
    raise ValueError("Original position snapshots are immutable")
