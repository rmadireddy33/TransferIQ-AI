import hashlib
import json
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.api.dependencies import fail
from backend.models.entities import (AuditEvent, BrokerageAccount, BrokerageFirm, Client,
                                     FirmType, IdempotencyRecord, Transfer, TransferStatus)
from backend.schemas.contracts import TransferCreate


def require_record(session: Session, model, identifier: str):
    record = session.get(model, identifier)
    if record is None:
        fail(404, "not_found", f"{model.__name__} '{identifier}' was not found")
    return record


def validate_references(session: Session, data: TransferCreate):
    # Invalid references in creation are 422; GET lookups use 404.
    refs = [(Client, data.client_id), (BrokerageFirm, data.delivering_firm_id),
            (BrokerageFirm, data.receiving_firm_id), (BrokerageAccount, data.source_account_id),
            (BrokerageAccount, data.destination_account_id)]
    records = []
    for model, identifier in refs:
        record = session.get(model, identifier)
        if record is None:
            fail(422, "invalid_reference", f"{model.__name__} '{identifier}' does not exist")
        records.append(record)
    client, delivering, receiving, source, destination = records
    if any(record.status != "ACTIVE" for record in (client, source, destination)):
        fail(422, "inactive_record", "Client and both accounts must be ACTIVE")
    if source.account_id == destination.account_id or delivering.firm_id == receiving.firm_id:
        fail(422, "invalid_route", "Source and destination accounts and firms must differ")
    if source.client_id != client.client_id or destination.client_id != client.client_id:
        fail(422, "client_mismatch", "Both accounts must belong to the transfer client")
    if source.firm_id != delivering.firm_id or destination.firm_id != receiving.firm_id:
        fail(422, "firm_mismatch", "Accounts must belong to their specified firms")
    if delivering.firm_type not in (FirmType.DELIVERING, FirmType.BOTH):
        fail(422, "invalid_firm_role", "Delivering firm cannot deliver")
    if receiving.firm_type not in (FirmType.RECEIVING, FirmType.BOTH):
        fail(422, "invalid_firm_role", "Receiving firm cannot receive")


def create_transfer(session: Session, data: TransferCreate, key: str | None):
    digest = hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    with session.begin():
        if key:
            existing = session.get(IdempotencyRecord, key)
            if existing:
                if existing.request_hash != digest:
                    fail(409, "idempotency_conflict", "Idempotency-Key already belongs to a different request")
                return require_record(session, Transfer, existing.transfer_id), False
        validate_references(session, data)
        transfer = Transfer(transfer_id=f"TRF-{uuid4()}", **data.model_dump(), status=TransferStatus.DRAFT)
        session.add(transfer)
        session.flush()
        session.add(AuditEvent(event_id=str(uuid4()), transfer_id=transfer.transfer_id,
                               actor="api-service", action="TRANSFER_CREATED", new_status="DRAFT"))
        if key:
            session.add(IdempotencyRecord(key=key, request_hash=digest, transfer_id=transfer.transfer_id))
    return transfer, True
