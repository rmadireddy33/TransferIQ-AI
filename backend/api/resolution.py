"""Capability-scoped demo writes; private operations never trust demo references."""
import secrets
from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request, Response
from backend.api.demo_execution import Context, CreateDemoRun, DemoRunResponse, manager
from backend.api.dependencies import fail, require_api_key
from backend.schemas.resolution import PlanPreview, PlanBinding, DecisionRequest
from backend.services import resolution as service
from sqlalchemy import select
from backend.models.entities import AuditEvent

router = APIRouter(prefix='/api/demo/runs', tags=['Isolated demo review - unverified identity'])
private_router = APIRouter(prefix='/api/resolution-plans', dependencies=[Depends(require_api_key)], tags=['Protected resolution boundary'])


class ReviewRunResponse(DemoRunResponse):
    review_capability: str


@router.post('/review', response_model=ReviewRunResponse, status_code=201)
def create_review(data: CreateDemoRun, request: Request, response: Response,
                  idempotency_key: Annotated[str, Header(min_length=16,max_length=128,pattern=r'^[A-Za-z0-9._:-]+$')]):
    value, created = manager(request).create(data.transfer_id, idempotency_key, with_review=True)
    response.status_code = 201 if created else 200
    response.headers['Cache-Control'] = 'no-store'
    return value


def review_context(ctx: Context, x_demo_capability: Annotated[str | None, Header()] = None):
    row, _, _ = ctx
    expected = row.get('review_token')
    if not expected or not x_demo_capability or not secrets.compare_digest(expected.encode(), x_demo_capability.encode()):
        fail(403, 'demo_capability_required', 'This write requires the capability issued to this review run creator')
    return ctx


ReviewContext = Annotated[tuple, Depends(review_context)]


@router.post('/{runId}/resolution-plans/preview')
def preview(data: PlanPreview, ctx: ReviewContext,
            idempotency_key: Annotated[str, Header(min_length=16,max_length=128,pattern=r'^[A-Za-z0-9._:-]+$')]):
    row, _, session = ctx
    plan = service.preview(session, row['transfer_id'], data, idempotency_key, row['expires_at'])
    return service.read_plan(session, plan)


@router.get('/{runId}/resolution-plans/{planId}')
def get(planId: str, ctx: Context):
    row, _, session = ctx
    return service.read_plan(session, service.get_plan(session, planId, row['transfer_id']))


@router.post('/{runId}/resolution-plans/{planId}/decision')
def decide(planId: str, data: DecisionRequest, ctx: ReviewContext):
    row, _, session = ctx
    return service.read_plan(session, service.record_decision(session, row['transfer_id'], planId, data))


@router.post('/{runId}/resolution-plans/{planId}/execute')
def execute(planId: str, data: PlanBinding, ctx: ReviewContext):
    row, _, session = ctx
    return service.read_plan(session, service.execute(session, row['transfer_id'], planId, data))


@router.get('/{runId}/resolution-plans/{planId}/verify')
def verify(planId: str, ctx: Context):
    row, _, session = ctx
    return service.verify(session, service.get_plan(session, planId, row['transfer_id']))


@router.get('/{runId}/resolution-plans/{planId}/audit')
def audit(planId: str, ctx: Context):
    row, _, session = ctx
    service.get_plan(session, planId, row['transfer_id'])
    records = session.scalars(select(AuditEvent).where(AuditEvent.plan_id == planId).order_by(AuditEvent.created_at)).all()
    return dict(demoOnly=True, identityVerification=service.LABEL, planId=planId,
        items=[dict(auditEventId=e.event_id,transferId=e.transfer_id,planId=e.plan_id,eventType=e.action,
                    eventData=e.event_data,correlationId=e.correlation_id,timestamp=e.created_at) for e in records])


@private_router.post('/preview')
@private_router.post('/{planId}/decision')
@private_router.post('/{planId}/execute')
def private_write_unavailable():
    fail(503, 'verified_review_not_configured', 'Privileged review is not configured; isolated demo references cannot authorize private changes')
