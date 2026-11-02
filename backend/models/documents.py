from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.entities import Base, enum_column
from backend.models.types import UTCDateTime, utcnow


class DocumentType(StrEnum):
    TRANSFER_REQUEST = "TRANSFER_REQUEST"
    ACCOUNT_STATEMENT = "ACCOUNT_STATEMENT"
    CORPORATE_ACTION_NOTICE = "CORPORATE_ACTION_NOTICE"
    COST_BASIS_STATEMENT = "COST_BASIS_STATEMENT"


class DocumentSource(StrEnum):
    CLIENT_UPLOAD = "CLIENT_UPLOAD"
    TRANSFER_OPERATIONS = "TRANSFER_OPERATIONS"
    DELIVERING_FIRM = "DELIVERING_FIRM"
    REFERENCE_DATA = "REFERENCE_DATA"


class TransferDocument(Base):
    __tablename__ = "transfer_documents"
    __table_args__ = (
        CheckConstraint("file_size > 0 AND version >= 1"),
        CheckConstraint("length(checksum_sha256) = 64"),
        CheckConstraint("mime_type = 'application/pdf'"),
        CheckConstraint("document_status IN ('PENDING', 'READY', 'FAILED')"),
        UniqueConstraint("sample_key", "version"),
    )
    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    transfer_id: Mapped[str] = mapped_column(ForeignKey("transfers.transfer_id"), index=True)
    document_type: Mapped[DocumentType] = mapped_column(enum_column(DocumentType), index=True)
    document_source: Mapped[DocumentSource] = mapped_column(enum_column(DocumentSource))
    file_name: Mapped[str] = mapped_column(String(64), unique=True)
    original_file_name: Mapped[str] = mapped_column(String(200))
    storage_path: Mapped[str] = mapped_column(String(256), unique=True)
    mime_type: Mapped[str] = mapped_column(String(64), default="application/pdf")
    file_size: Mapped[int] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    document_status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    is_sample: Mapped[bool] = mapped_column(Boolean(create_constraint=True), default=False)
    evaluation_only: Mapped[bool] = mapped_column(Boolean(create_constraint=True), default=False)
    sample_key: Mapped[str | None] = mapped_column(String(256), index=True)
    seed_key: Mapped[str | None] = mapped_column(String(64), unique=True)
