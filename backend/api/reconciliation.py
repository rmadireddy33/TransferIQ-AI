from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy import select

from backend.api.dependencies import DatabaseSession, Pagination, require_api_key
from backend.api.routes import page
from backend.models.entities import Security
from backend.models.reconciliation import CorporateAction, ReconciliationRun, SecurityIdentifierMapping, TransferException
from backend.schemas.contracts import ErrorResponse, Page
from backend.schemas.reconciliation import (CorporateActionResponse, ExceptionPage, ExceptionResponse,
    IdentifierMappingResponse, PositionResult, ReconcileRequest, ReconciliationResponse)
from backend.services.reconciliation import latest_run, reconcile, snapshot
from backend.services.transfers import require_record

router = APIRouter(tags=["Reconciliation"], dependencies=[Depends(require_api_key)],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse},
               409: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})


def exception_response(row):
    return {**snapshot(row), "normalized_quantity": row.expected_quantity, "status": row.resolution_status}


def run_response(session, run):
    exceptions = session.scalars(select(TransferException).where(
        TransferException.reconciliation_run_id == run.reconciliation_run_id).order_by(
        TransferException.security_id, TransferException.exception_type)).all()
    fields = ("reconciliation_run_id", "transfer_id", "status", "execution_status", "source_snapshot_version",
              "target_snapshot_version", "input_fingerprint", "started_at", "completed_at", "last_requested_at")
    return {**{field: getattr(run, field) for field in fields},
        "rule_version": run.input_data["rule_version"], "source_snapshot_date": run.input_data["source_date"],
        "target_snapshot_dates": sorted({r["snapshot_date"] for r in run.input_data["target"] if r["snapshot_date"]}),
        "summary": {"total_positions": run.total_positions, "directly_matched": run.directly_matched,
                    "evidence_explained": run.evidence_explained, "unresolved": run.unresolved_count,
                    "cost_basis_issues": run.cost_basis_issues},
        "positions": [{key: row.get(key) for key in PositionResult.model_fields} for row in run.position_results],
        "exceptions": [exception_response(row) for row in exceptions]}


@router.post("/api/transfers/{transferId}/reconcile", response_model=ReconciliationResponse, status_code=201,
             responses={200: {"model": ReconciliationResponse, "description": "Completed result reused"}})
def run_reconciliation(transferId: str, session: DatabaseSession, response: Response,
                       body: ReconcileRequest | None = Body(default=None)):
    run, created = reconcile(session, transferId, body.source_snapshot_date if body else None)
    response.status_code = 201 if created else 200
    response.headers["Location"] = f"/api/reconciliation-runs/{run.reconciliation_run_id}"
    return run_response(session, run)


@router.get("/api/transfers/{transferId}/reconciliation", response_model=ReconciliationResponse)
def get_latest_reconciliation(transferId: str, session: DatabaseSession):
    return run_response(session, latest_run(session, transferId))


@router.get("/api/transfers/{transferId}/exceptions", response_model=ExceptionPage)
def get_exceptions(transferId: str, session: DatabaseSession, bounds: Pagination):
    run = latest_run(session, transferId)
    result = page(session, select(TransferException).where(TransferException.reconciliation_run_id == run.reconciliation_run_id)
                  .order_by(TransferException.security_id, TransferException.exception_type), bounds)
    return {**result, "items": [exception_response(row) for row in result["items"]],
            "reconciliation_run_id": run.reconciliation_run_id}


@router.get("/api/reconciliation-runs/{runId}", response_model=ReconciliationResponse)
def get_run(runId: str, session: DatabaseSession):
    return run_response(session, require_record(session, ReconciliationRun, runId))


@router.get("/api/corporate-actions", response_model=Page[CorporateActionResponse])
def get_actions(session: DatabaseSession, bounds: Pagination):
    return page(session, select(CorporateAction).order_by(CorporateAction.effective_date, CorporateAction.corporate_action_id), bounds)


@router.get("/api/securities/{securityId}/corporate-actions", response_model=Page[CorporateActionResponse])
def get_security_actions(securityId: str, session: DatabaseSession, bounds: Pagination):
    require_record(session, Security, securityId)
    return page(session, select(CorporateAction).where(CorporateAction.security_id == securityId)
                .order_by(CorporateAction.effective_date, CorporateAction.corporate_action_id), bounds)


@router.get("/api/securities/{securityId}/identifier-mappings", response_model=Page[IdentifierMappingResponse])
def get_mappings(securityId: str, session: DatabaseSession, bounds: Pagination):
    require_record(session, Security, securityId)
    return page(session, select(SecurityIdentifierMapping).where(SecurityIdentifierMapping.canonical_security_id == securityId)
                .order_by(SecurityIdentifierMapping.effective_date, SecurityIdentifierMapping.mapping_id), bounds)
