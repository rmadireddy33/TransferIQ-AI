from datetime import date, datetime
from decimal import Decimal

from backend.schemas.contracts import Contract, Page


class ReconcileRequest(Contract):
    source_snapshot_date: date | None = None


class ReconciliationSummary(Contract):
    total_positions: int
    directly_matched: int
    evidence_explained: int
    unresolved: int
    cost_basis_issues: int


class ExceptionResponse(Contract):
    exception_id: str
    reconciliation_run_id: str
    transfer_id: str
    security_id: str | None
    exception_type: str
    severity: str
    source_quantity: Decimal | None
    target_quantity: Decimal | None
    expected_quantity: Decimal | None
    normalized_quantity: Decimal | None
    difference: Decimal | None
    description: str
    evidence_references: list[str]
    resolution_status: str
    status: str
    created_at: datetime
    updated_at: datetime


class PositionResult(Contract):
    security_id: str
    classification: str
    source_quantity: Decimal | None = None
    target_quantity: Decimal | None = None
    expected_quantity: Decimal | None = None
    difference: Decimal | None = None
    evidence_references: list[str]


class ReconciliationResponse(Contract):
    reconciliation_run_id: str
    transfer_id: str
    status: str
    execution_status: str
    source_snapshot_version: str
    target_snapshot_version: str
    input_fingerprint: str
    rule_version: str
    source_snapshot_date: date
    target_snapshot_dates: list[date]
    started_at: datetime
    completed_at: datetime
    last_requested_at: datetime
    summary: ReconciliationSummary
    positions: list[PositionResult]
    exceptions: list[ExceptionResponse]


class ExceptionPage(Page[ExceptionResponse]):
    reconciliation_run_id: str


class CorporateActionResponse(Contract):
    corporate_action_id: str
    security_id: str
    action_type: str
    numerator: int
    denominator: int
    effective_date: date
    verified: bool
    evidence_reference: str | None
    created_at: datetime


class IdentifierMappingResponse(Contract):
    mapping_id: str
    old_identifier: str
    new_identifier: str
    canonical_security_id: str
    effective_date: date
    verified: bool
    evidence_reference: str | None
