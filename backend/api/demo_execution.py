"""Anonymous allowlisted synthetic operations; no private session dependency."""
from typing import Annotated, Literal
from datetime import date, datetime
from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import func, select

from backend.api import routes, reconciliation, documents
from backend.api.dependencies import Pagination, fail
from backend.models.entities import Transfer, AuditEvent, Security, PositionSnapshot, ReceivingTransferStagingPosition
from backend.models.reconciliation import CorporateAction, SecurityIdentifierMapping, CostBasisRecord
from backend.models.documents import TransferDocument
from backend.schemas.contracts import Contract, TransferResponse, Page, PositionResponse, StagingPage, SecurityResponse
from backend.schemas.documents import DocumentResponse
from backend.schemas.reconciliation import ReconciliationResponse, ExceptionPage, CorporateActionResponse, IdentifierMappingResponse
from decimal import Decimal
from backend.services.document_storage import read_document

router = APIRouter(prefix='/api/demo/runs', tags=['Live synthetic demo execution'])


class CreateDemoRun(Contract):
    transfer_id: Literal['TRF-1001', 'TRF-1002', 'TRF-1003', 'TRF-1004', 'TRF-1005']


class DemoRunResponse(Contract):
    run_id: str
    transfer_id: str
    expires_at: float
    fictional_demo: Literal[True]
    evidence_mode: Literal['LIVE_SYNTHETIC_BACKEND']


class AuditItem(Contract):
    action: str
    created_at: datetime


class DemoAudit(Contract):
    run_id: str
    transfer_id: str
    fictional_demo: Literal[True] = True
    evidence_mode: Literal['LIVE_SYNTHETIC_BACKEND'] = 'LIVE_SYNTHETIC_BACKEND'
    corrections_applied: Literal[0] = 0
    maestro_execution_verified: Literal[False] = False
    items: list[AuditItem]


class EmptyRequest(Contract):
    pass


class DemoCorporateAction(CorporateActionResponse):
    security_name: str
    notice_date: date
    notice_date_source: Literal['REFERENCE_CREATED_AT'] = 'REFERENCE_CREATED_AT'


class DemoCorporateActions(Page[DemoCorporateAction]):
    transfer_id: str
    run_id: str
    fictional_demo: Literal[True] = True
    reference_source: Literal['SEEDED_REFERENCE_DATABASE'] = 'SEEDED_REFERENCE_DATABASE'


class DemoCostBasis(Contract):
    cost_basis_id: str
    transfer_id: str
    security_id: str
    quantity: Decimal | None
    acquisition_date: date | None
    cost_basis_amount: Decimal | None
    status: str
    evidence_reference: str | None


class InvestigationReferences(Contract):
    contract_version: Literal['1.0'] = '1.0'
    run_id: str
    transfer_id: str
    fictional_demo: Literal[True] = True
    securities: list[SecurityResponse]
    identifier_mappings: list[IdentifierMappingResponse]
    cost_basis: list[DemoCostBasis]


def manager(request: Request):
    if not request.app.state.settings.demo_execution_enabled:
        fail(404, 'not_found', 'Public demo execution is disabled')
    return request.app.state.demo_runs


def context(runId: str, request: Request, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-TransferIQ-Evidence'] = 'live-synthetic-backend'
    with manager(request).open(runId) as value:
        yield value


Context = Annotated[tuple, Depends(context)]


@router.post('', response_model=DemoRunResponse, status_code=201)
def create(data: CreateDemoRun, request: Request, response: Response,
           idempotency_key: Annotated[str, Header(min_length=16, max_length=128,
               pattern=r'^[A-Za-z0-9._:-]+$')]):
    result, created = manager(request).create(data.transfer_id, idempotency_key)
    response.status_code = 201 if created else 200
    response.headers['Location'] = f"/api/demo/runs/{result['runId']}/transfer"
    response.headers['Cache-Control'] = 'no-store'
    return result


@router.get('/{runId}/transfer', response_model=TransferResponse)
def transfer(ctx: Context):
    row, _, session = ctx
    return routes.transfer(row['transfer_id'], session)


@router.get('/{runId}/delivering/accounts/{accountId}/positions', response_model=Page[PositionResponse])
def source(accountId: str, ctx: Context, bounds: Pagination):
    row, _, session = ctx
    transfer = session.get(Transfer, row['transfer_id'])
    if accountId != transfer.source_account_id:
        fail(404, 'not_found', 'Account is outside this synthetic run')
    return routes.source_positions(accountId, session, bounds)


@router.get('/{runId}/receiving/accounts/{accountId}/positions', response_model=StagingPage)
def target(accountId: str, ctx: Context, bounds: Pagination):
    row, _, session = ctx
    transfer = session.get(Transfer, row['transfer_id'])
    if accountId != transfer.destination_account_id:
        fail(404, 'not_found', 'Account is outside this synthetic run')
    return routes.receiving_positions(accountId, session, bounds, row['transfer_id'])


@router.post('/{runId}/reconcile', response_model=ReconciliationResponse)
def reconcile(ctx: Context, response: Response, data: EmptyRequest):
    row, _, session = ctx
    result = reconciliation.run_reconciliation(row['transfer_id'], session, response, None)
    response.headers['Location'] = f"/api/demo/runs/{row['run_id']}/reconciliation"
    return result


@router.get('/{runId}/reconciliation', response_model=ReconciliationResponse)
def result(ctx: Context):
    row, _, session = ctx
    return reconciliation.get_latest_reconciliation(row['transfer_id'], session)


@router.get('/{runId}/exceptions', response_model=ExceptionPage)
def exceptions(ctx: Context, bounds: Pagination):
    row, _, session = ctx
    return reconciliation.get_exceptions(row['transfer_id'], session, bounds)


@router.get('/{runId}/documents', response_model=Page[DocumentResponse])
def sample_documents(ctx: Context, bounds: Pagination):
    row, _, session = ctx
    return documents.list_documents(row['transfer_id'], session, bounds)


@router.get('/{runId}/corporate-actions', response_model=DemoCorporateActions)
def corporate_actions(ctx: Context, bounds: Pagination):
    """Independent read-only reference evidence, scoped to this run's securities.

    Never reads a PDF or accepts extraction fields. The synthetic notice date
    uses the same documented reference timestamp as the existing PDF generator.
    """
    row, _, session = ctx
    transfer = session.get(Transfer, row['transfer_id'])
    security_ids = select(PositionSnapshot.security_id).where(
        PositionSnapshot.account_id == transfer.source_account_id).union(
        select(ReceivingTransferStagingPosition.security_id).where(
            ReceivingTransferStagingPosition.transfer_id == transfer.transfer_id))
    predicate = CorporateAction.security_id.in_(security_ids)
    total = session.scalar(select(func.count()).select_from(CorporateAction).where(predicate))
    records = session.execute(select(CorporateAction, Security.security_name)
        .join(Security, Security.security_id == CorporateAction.security_id).where(predicate)
        .order_by(CorporateAction.corporate_action_id).limit(bounds['limit']).offset(bounds['offset'])).all()
    return DemoCorporateActions(transfer_id=transfer.transfer_id, run_id=row['run_id'],
        total=total, **bounds, items=[DemoCorporateAction(
            **CorporateActionResponse.model_validate(action).model_dump(),
            security_name=name, notice_date=action.created_at.date()) for action, name in records])


@router.get('/{runId}/documents/{documentId}/download', response_class=Response)
def pdf(documentId: str, ctx: Context):
    row, settings, session = ctx
    document = session.get(TransferDocument, documentId)
    if not document or document.transfer_id != row['transfer_id'] or not document.is_sample or document.evaluation_only:
        fail(404, 'not_found', 'Unknown synthetic document')
    return Response(read_document(settings, document), media_type='application/pdf', headers={
        'Content-Disposition': 'attachment; filename="fictional-demo.pdf"',
        'X-Checksum-SHA256': document.checksum_sha256, 'X-Content-Type-Options': 'nosniff',
        'Cache-Control': 'no-store'})


@router.get('/{runId}/investigation-references', response_model=InvestigationReferences)
def investigation_references(ctx: Context):
    """Bounded, read-only evidence from the selected synthetic run only."""
    row, _, session = ctx
    transfer = session.get(Transfer, row['transfer_id'])
    ids = select(PositionSnapshot.security_id).where(
        PositionSnapshot.account_id == transfer.source_account_id).union(
        select(ReceivingTransferStagingPosition.security_id).where(
            ReceivingTransferStagingPosition.transfer_id == transfer.transfer_id))
    securities = session.scalars(select(Security).where(Security.security_id.in_(ids))
        .order_by(Security.security_id).limit(101)).all()
    mappings = session.scalars(select(SecurityIdentifierMapping).where(
        SecurityIdentifierMapping.canonical_security_id.in_(ids))
        .order_by(SecurityIdentifierMapping.mapping_id).limit(101)).all()
    basis = session.scalars(select(CostBasisRecord).where(
        CostBasisRecord.transfer_id == transfer.transfer_id)
        .order_by(CostBasisRecord.cost_basis_id).limit(101)).all()
    if any(len(records) > 100 for records in (securities, mappings, basis)):
        fail(422, 'reference_limit_exceeded', 'Synthetic reference context exceeds the bounded contract')
    return InvestigationReferences(run_id=row['run_id'], transfer_id=transfer.transfer_id,
        securities=securities, identifier_mappings=mappings, cost_basis=basis)


@router.get('/{runId}/audit', response_model=DemoAudit)
def audit(ctx: Context):
    row, _, session = ctx
    events = session.scalars(select(AuditEvent).where(AuditEvent.transfer_id == row['transfer_id'])
                            .order_by(AuditEvent.created_at).limit(100)).all()
    return DemoAudit(run_id=row['run_id'], transfer_id=row['transfer_id'], items=[
        AuditItem(action=x.action, created_at=x.created_at) for x in events])
