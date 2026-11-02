from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.models.entities import FirmType, TransferType, TransferStatus


class Contract(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel,
                              populate_by_name=True, extra="forbid")


class ClientResponse(Contract):
    client_id: str
    first_name: str
    last_name: str
    email: str
    status: str
    created_at: datetime


class FirmResponse(Contract):
    firm_id: str
    firm_name: str
    firm_type: FirmType
    created_at: datetime


class AccountResponse(Contract):
    account_id: str
    client_id: str
    firm_id: str
    account_number: str
    account_type: str
    status: str
    created_at: datetime


class TransferCreate(Contract):
    client_id: str = Field(min_length=1, max_length=64)
    delivering_firm_id: str = Field(min_length=1, max_length=64)
    receiving_firm_id: str = Field(min_length=1, max_length=64)
    source_account_id: str = Field(min_length=1, max_length=64)
    destination_account_id: str = Field(min_length=1, max_length=64)
    transfer_type: TransferType


class TransferResponse(TransferCreate):
    transfer_id: str
    simulated_acats_control_number: str | None
    status: TransferStatus
    created_at: datetime
    updated_at: datetime


class SecurityResponse(Contract):
    security_id: str
    symbol: str
    security_name: str
    security_type: str
    canonical_identifier: str
    status: str


class PositionResponse(Contract):
    position_id: str
    account_id: str
    security_id: str
    quantity: Decimal
    snapshot_date: date
    source_system: str
    observed_identifier: str | None = None
    created_at: datetime


class StagingResponse(Contract):
    staging_position_id: str
    transfer_id: str
    security_id: str
    quantity: Decimal
    status: str
    version: int
    snapshot_date: date | None = None
    observed_identifier: str | None = None
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class Page(Contract, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class StagingPage(Page[StagingResponse]):
    position_kind: Literal["RECEIVING_TRANSFER_STAGING"] = "RECEIVING_TRANSFER_STAGING"
    settled_holdings: Literal[False] = False


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    fictional_demo: Literal[True] = True


class ErrorDetail(Contract):
    code: str
    message: str


class ErrorResponse(Contract):
    detail: ErrorDetail
