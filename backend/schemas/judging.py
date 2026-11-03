"""Explicit public fields: no live database identifiers, files, or execution claims."""
from typing import Literal
from pydantic import Field
from backend.schemas.contracts import Contract


class DemoPosition(Contract):
    security_id: str
    classification: Literal['MATCHED', 'EXPLAINED', 'UNRESOLVED']
    source_quantity: str | None
    target_quantity: str | None
    expected_quantity: str | None
    difference: str | None


class DemoException(Contract):
    security_id: str | None
    exception_type: str
    resolution_status: str
    description: str


class DemoTransfer(Contract):
    transfer_id: Literal['TRF-1001', 'TRF-1002', 'TRF-1003', 'TRF-1004', 'TRF-1005']
    title: str
    evidence_mode: Literal['PRECOMPUTED_SYNTHETIC_SAMPLE'] = 'PRECOMPUTED_SYNTHETIC_SAMPLE'
    live_execution: Literal[False] = False
    reconciliation_run_id: None = None
    rule_version: str
    total_positions: int = Field(ge=0)
    directly_matched: int = Field(ge=0)
    evidence_explained: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    cost_basis_issues: int = Field(ge=0)
    expected_workflow_outcome: Literal['CLEAN', 'INVESTIGATION_REQUIRED']
    requires_cost_basis_review: bool
    quantity_reconciliation_only: Literal[True] = True
    positions: list[DemoPosition]
    exceptions: list[DemoException]


class DemoCatalog(Contract):
    fictional_demo: Literal[True] = True
    read_only: Literal[True] = True
    evidence_mode: Literal['PRECOMPUTED_SYNTHETIC_SAMPLE'] = 'PRECOMPUTED_SYNTHETIC_SAMPLE'
    notice: str = 'Offline fictional fixture results, not live Maestro executions. CLEAN describes quantities only; cost basis may still require review. No custody correction or settlement occurs.'
    items: list[DemoTransfer] = Field(min_length=5, max_length=5)
