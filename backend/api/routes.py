from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, Request
from sqlalchemy import func, select, text

from backend.api.dependencies import DatabaseSession, Pagination, fail, require_api_key
from backend.models.entities import (BrokerageAccount, BrokerageFirm, Client, FirmType,
                                     PositionSnapshot, ReceivingTransferStagingPosition,
                                     Security, Transfer)
from backend.schemas.contracts import (AccountResponse, ClientResponse, ErrorResponse,
    FirmResponse, HealthResponse, Page, PositionResponse, SecurityResponse, StagingPage,
    TransferCreate, TransferResponse)
from backend.services.transfers import create_transfer, require_record

router = APIRouter(responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})


def page(session, statement, bounds):
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    items = session.scalars(statement.limit(bounds["limit"]).offset(bounds["offset"])).all()
    return {"items": items, "total": total, **bounds}


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health(request: Request, session: DatabaseSession):
    if not request.app.state.ready:
        fail(503, 'not_ready', 'Application initialization is incomplete')
    session.execute(text("SELECT 1"))
    return HealthResponse()


@router.get("/api/clients", response_model=Page[ClientResponse], tags=["Clients"])
def clients(session: DatabaseSession, bounds: Pagination):
    return page(session, select(Client).order_by(Client.client_id), bounds)


@router.get("/api/clients/{clientId}", response_model=ClientResponse, tags=["Clients"])
def client(clientId: str, session: DatabaseSession):
    return require_record(session, Client, clientId)


@router.get("/api/firms", response_model=Page[FirmResponse], tags=["Firms"])
def firms(session: DatabaseSession, bounds: Pagination):
    return page(session, select(BrokerageFirm).order_by(BrokerageFirm.firm_id), bounds)


@router.get("/api/accounts/{accountId}", response_model=AccountResponse, tags=["Accounts"])
def account(accountId: str, session: DatabaseSession):
    return require_record(session, BrokerageAccount, accountId)


@router.post("/api/transfers", response_model=TransferResponse, status_code=201,
             dependencies=[Depends(require_api_key)], tags=["Transfers"],
             responses={200: {"model": TransferResponse, "description": "Idempotent replay"},
                        401: {"model": ErrorResponse}, 409: {"model": ErrorResponse}})
def new_transfer(data: TransferCreate, session: DatabaseSession, response: Response,
                 idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128,
                     pattern=r"^[A-Za-z0-9._:-]+$")] = None):
    transfer, created = create_transfer(session, data, idempotency_key)
    response.status_code = 201 if created else 200
    response.headers["Location"] = f"/api/transfers/{transfer.transfer_id}"
    return transfer


@router.get("/api/transfers", response_model=Page[TransferResponse], tags=["Transfers"])
def transfers(session: DatabaseSession, bounds: Pagination):
    return page(session, select(Transfer).order_by(Transfer.transfer_id), bounds)


@router.get("/api/transfers/{transferId}", response_model=TransferResponse, tags=["Transfers"])
def transfer(transferId: str, session: DatabaseSession):
    return require_record(session, Transfer, transferId)


@router.get("/api/transfers/{transferId}/assets", response_model=StagingPage, tags=["Transfers"])
def transfer_assets(transferId: str, session: DatabaseSession, bounds: Pagination):
    require_record(session, Transfer, transferId)
    model = ReceivingTransferStagingPosition
    return page(session, select(model).where(model.transfer_id == transferId).order_by(model.security_id), bounds)


@router.get("/api/delivering/accounts/{accountId}/positions", response_model=Page[PositionResponse], tags=["Delivering"])
def source_positions(accountId: str, session: DatabaseSession, bounds: Pagination):
    account = require_record(session, BrokerageAccount, accountId)
    if account.firm.firm_type not in (FirmType.DELIVERING, FirmType.BOTH):
        fail(422, "invalid_firm_role", "Account is not at a delivering firm")
    model = PositionSnapshot
    latest = select(func.max(model.snapshot_date)).where(model.account_id == accountId).scalar_subquery()
    return page(session, select(model).where(model.account_id == accountId, model.snapshot_date == latest)
                .order_by(model.security_id, model.source_system), bounds)


@router.get("/api/receiving/accounts/{accountId}/positions", response_model=StagingPage, tags=["Receiving"])
def receiving_positions(accountId: str, session: DatabaseSession, bounds: Pagination,
                        transferId: str | None = Query(default=None)):
    account = require_record(session, BrokerageAccount, accountId)
    if account.firm.firm_type not in (FirmType.RECEIVING, FirmType.BOTH):
        fail(422, "invalid_firm_role", "Account is not at a receiving firm")
    model = ReceivingTransferStagingPosition
    statement = select(model).join(Transfer).where(Transfer.destination_account_id == accountId)
    if transferId is not None:
        transfer = require_record(session, Transfer, transferId)
        if transfer.destination_account_id != accountId:
            fail(422, "account_mismatch", "Transfer does not target this receiving account")
        statement = statement.where(model.transfer_id == transferId)
    return page(session, statement.order_by(model.transfer_id, model.security_id), bounds)


@router.get("/api/securities", response_model=Page[SecurityResponse], tags=["Securities"])
def securities(session: DatabaseSession, bounds: Pagination):
    return page(session, select(Security).order_by(Security.security_id), bounds)


@router.get("/api/securities/{securityId}", response_model=SecurityResponse, tags=["Securities"])
def security(securityId: str, session: DatabaseSession):
    return require_record(session, Security, securityId)
