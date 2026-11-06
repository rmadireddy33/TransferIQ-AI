from typing import Literal
from pydantic import Field
from backend.schemas.contracts import Contract

Disposition = Literal['ACCEPT_VERIFIED_EXPLANATION', 'REQUEST_ADDITIONAL_EVIDENCE',
    'ESCALATE_TO_TRANSFER_OPERATIONS', 'OPEN_COST_BASIS_CASE', 'REJECT_PROPOSED_PLAN']


class ProposedAction(Contract):
    exception_id: str = Field(min_length=1, max_length=64)
    security_id: str = Field(min_length=1, max_length=64)
    disposition: Disposition
    evidence_references: list[str] = Field(max_length=30)


class PlanPreview(Contract):
    transfer_id: str = Field(min_length=1, max_length=64)
    reconciliation_run_id: str = Field(min_length=1, max_length=64)
    agent_investigation_id: str = Field(min_length=1, max_length=128)
    investigation_summary: str = Field(min_length=1, max_length=8000)
    overall_risk_level: Literal['LOW','MEDIUM','HIGH']
    document_evidence_status: Literal['NOT_PROCESSED_IXP_DISABLED']
    proposed_actions: list[ProposedAction] = Field(min_length=1, max_length=100)


class PlanBinding(Contract):
    plan_version: int = Field(ge=1)
    plan_hash: str = Field(pattern=r'^[0-9a-f]{64}$')


class DecisionRequest(PlanBinding):
    review_outcome: Literal['APPROVE','REQUEST_EVIDENCE','ESCALATE','REJECT']
    reviewer_reference: str = Field(min_length=1, max_length=256)
    reviewer_comments: str = Field(default='', max_length=2000)
    additional_information: str = Field(default='', max_length=2000)
    review_event_reference: str = Field(min_length=1, max_length=256)
