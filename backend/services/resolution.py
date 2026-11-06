"""Deterministic, isolated demo dispositions. Never changes financial records."""
from uuid import uuid4
from sqlalchemy import select, func
from backend.api.dependencies import fail
from backend.models.entities import Transfer, AuditEvent
from backend.models.reconciliation import ReconciliationRun, TransferException, CorporateAction, SecurityIdentifierMapping
from backend.models.resolution import ResolutionPlan, ReviewDecision, DemoDisposition
from backend.models.types import utcnow
from backend.services.reconciliation import collect_inputs, fingerprint, latest_run, snapshot
from backend.schemas.reconciliation import ExceptionResponse

LABEL = 'UNVERIFIED_DEMO_REFERENCE'


def get_plan(session, plan_id, transfer_id):
    plan = session.get(ResolutionPlan, plan_id)
    if not plan or plan.transfer_id != transfer_id:
        fail(404, 'not_found', 'Plan is outside this synthetic run')
    return plan


def current(session, plan):
    transfer = session.get(Transfer, plan.transfer_id)
    run = latest_run(session, plan.transfer_id)
    if run.reconciliation_run_id != plan.reconciliation_run_id or fingerprint(collect_inputs(session, transfer)) != plan.context['inputFingerprint']:
        fail(409, 'stale_plan', 'Reconciliation or evidence changed; create a new plan and review it')
    exceptions = session.scalars(select(TransferException).where(
        TransferException.reconciliation_run_id == run.reconciliation_run_id).order_by(TransferException.exception_id)).all()
    if fingerprint([snapshot(e) for e in exceptions]) != plan.context['exceptionsFingerprint']:
        fail(409, 'stale_plan', 'Exception state changed after preview')
    if plan.plan_hash != fingerprint(plan.context['hashContent']):
        fail(409, 'plan_integrity', 'Stored plan content failed integrity verification')
    return run, exceptions


def validate_actions(session, exceptions, proposed):
    by_id = {e.exception_id:e for e in exceptions}
    if len(proposed) != len(by_id) or {p['exceptionId'] for p in proposed} != set(by_id):
        fail(422, 'invalid_exception', 'Plan must cover every current exception exactly once')
    for p in proposed:
        e = by_id[p['exceptionId']]
        if p['securityId'] != e.security_id:
            fail(422, 'invalid_security', 'Security does not match the exception')
        refs = p['evidenceReferences']
        if len(refs) != len(set(refs)) or not set(refs).issubset(e.evidence_references):
            fail(422, 'invalid_evidence', 'Evidence does not belong to the exception')
        action = p['disposition']
        if action == 'ACCEPT_VERIFIED_EXPLANATION':
            if e.resolution_status != 'EXPLAINED' or not refs or set(refs) != set(e.evidence_references):
                fail(422, 'unsupported_disposition', 'Only independently explained exceptions can be acknowledged')
            valid = set()
            for ca in session.scalars(select(CorporateAction).where(CorporateAction.security_id == e.security_id, CorporateAction.verified.is_(True))):
                valid.update((ca.corporate_action_id, ca.evidence_reference))
            for mapping in session.scalars(select(SecurityIdentifierMapping).where(SecurityIdentifierMapping.canonical_security_id == e.security_id, SecurityIdentifierMapping.verified.is_(True))):
                valid.update((mapping.mapping_id, mapping.evidence_reference))
            if not set(refs).issubset(valid):
                fail(422, 'missing_evidence', 'Verified reference evidence is unavailable')
        elif action == 'OPEN_COST_BASIS_CASE':
            if not e.exception_type.startswith('COST_BASIS_') or e.resolution_status == 'EXPLAINED':
                fail(422, 'unsupported_disposition', 'Only an open cost-basis exception can open a basis case')
        elif action not in ('REQUEST_ADDITIONAL_EVIDENCE','ESCALATE_TO_TRANSFER_OPERATIONS'):
            fail(422, 'unsupported_disposition', 'The proposed disposition is not permitted')


def audit(session, plan, event_type, data):
    transfer = session.get(Transfer, plan.transfer_id)
    session.add(AuditEvent(event_id='AUD-'+str(uuid4()), transfer_id=plan.transfer_id,
        actor='isolated-demo', action=event_type, previous_status=transfer.status.value,
        new_status=transfer.status.value, plan_id=plan.plan_id, correlation_id=plan.agent_investigation_id,
        event_data={'demoOnly': True, 'identityVerification': LABEL, **data}))


def preview(session, transfer_id, data, key, expires_at):
    payload = data.model_dump(mode='json', by_alias=True)
    digest = fingerprint(payload)
    with session.begin():
        if data.transfer_id != transfer_id:
            fail(404, 'not_found', 'Transfer is outside this synthetic run')
        old = session.scalar(select(ResolutionPlan).where(ResolutionPlan.request_key == key))
        if old:
            if old.request_hash != digest:
                fail(409, 'idempotency_conflict', 'Idempotency key has different plan content')
            current(session, old)
            return old
        if session.scalar(select(func.count()).select_from(ResolutionPlan)) >= 5:
            fail(429, 'plan_quota', 'At most five plans are allowed per synthetic run')
        run = latest_run(session, transfer_id)
        if run.reconciliation_run_id != data.reconciliation_run_id:
            fail(409, 'stale_plan', 'Preview requires the latest reconciliation run')
        transfer = session.get(Transfer, transfer_id)
        inputs = collect_inputs(session, transfer)
        if fingerprint(inputs) != run.input_fingerprint:
            fail(409, 'stale_plan', 'Run reconciliation again before previewing a plan')
        exceptions = session.scalars(select(TransferException).where(
            TransferException.reconciliation_run_id == run.reconciliation_run_id).order_by(TransferException.exception_id)).all()
        actions = payload['proposedActions']
        validate_actions(session, exceptions, actions)
        pid = 'PLAN-'+str(uuid4())
        content = dict(payload, planId=pid, planVersion=1, inputFingerprint=run.input_fingerprint,
                       expiresAt=expires_at, identityVerification=LABEL)
        plan = ResolutionPlan(plan_id=pid, transfer_id=transfer_id, reconciliation_run_id=run.reconciliation_run_id,
            agent_investigation_id=data.agent_investigation_id, plan_hash=fingerprint(content),
            proposed_actions=actions, evidence_references=sorted({x for a in actions for x in a['evidenceReferences']}),
            request_key=key, request_hash=digest, context=dict(hashContent=content, inputFingerprint=run.input_fingerprint,
                exceptionsFingerprint=fingerprint([snapshot(e) for e in exceptions]), source=inputs['source'], target=inputs['target'],
                investigationSummary=data.investigation_summary, overallRiskLevel=data.overall_risk_level,
                documentEvidenceStatus=data.document_evidence_status, clientReference=transfer.client_id))
        session.add(plan)
        session.flush()
        audit(session, plan, 'PLAN_PREVIEWED', {'planHash':plan.plan_hash,'proposedActions':actions})
    return plan


def binding(plan, data):
    if data.plan_version != plan.plan_version or data.plan_hash != plan.plan_hash:
        fail(409, 'plan_binding_mismatch', 'Decision must match the exact reviewed plan version and hash')


def record_decision(session, transfer_id, plan_id, data):
    digest = fingerprint(data.model_dump(mode='json', by_alias=True))
    with session.begin():
        plan = get_plan(session, plan_id, transfer_id)
        binding(plan, data)
        current(session, plan)
        existing = session.scalar(select(ReviewDecision).where(ReviewDecision.plan_id == plan_id))
        if existing:
            if existing.request_hash != digest:
                fail(409, 'decision_conflict', 'This exact plan already has a different decision')
            return plan
        if plan.status != 'PREVIEWED':
            fail(409, 'invalid_plan_state', 'Plan is not awaiting a decision')
        if session.scalar(select(ReviewDecision).where(ReviewDecision.review_event_reference == data.review_event_reference)):
            fail(409, 'review_event_replayed', 'This demo review event was already bound to another plan')
        decision = ReviewDecision(decision_id='DEC-'+str(uuid4()), plan_id=plan_id,
            review_outcome=data.review_outcome, reviewer_reference=data.reviewer_reference,
            reviewer_comments=data.reviewer_comments, additional_information=data.additional_information,
            review_event_reference=data.review_event_reference, request_hash=digest)
        session.add(decision)
        plan.status, plan.updated_at = 'DECIDED', utcnow()
        audit(session, plan, 'DEMO_REVIEW_RECORDED', {'decisionId':decision.decision_id,'reviewOutcome':data.review_outcome,
            'planHash':plan.plan_hash, 'reviewEventReference':data.review_event_reference})
    return plan


def effective_actions(plan, decision):
    if decision.review_outcome == 'REJECT':
        return []
    override = {'REQUEST_EVIDENCE':'REQUEST_ADDITIONAL_EVIDENCE','ESCALATE':'ESCALATE_TO_TRANSFER_OPERATIONS'}.get(decision.review_outcome)
    return [dict(p, disposition=override or p['disposition']) for p in plan.proposed_actions]


def execute(session, transfer_id, plan_id, data):
    with session.begin():
        plan = get_plan(session, plan_id, transfer_id)
        binding(plan, data)
        _, exceptions = current(session, plan)
        decision = session.scalar(select(ReviewDecision).where(ReviewDecision.plan_id == plan_id))
        if not decision or plan.status == 'PREVIEWED':
            fail(409, 'decision_required', 'A recorded demo review is required')
        if plan.status in ('EXECUTED','REJECTED'):
            return plan
        actions = effective_actions(plan, decision)
        if actions:
            validate_actions(session, exceptions, actions)
        for p in actions:
            state = {'ACCEPT_VERIFIED_EXPLANATION':'ACKNOWLEDGED','REQUEST_ADDITIONAL_EVIDENCE':'EVIDENCE_REQUESTED',
                'ESCALATE_TO_TRANSFER_OPERATIONS':'OPEN_ESCALATED','OPEN_COST_BASIS_CASE':'OPEN_BASIS_CASE'}[p['disposition']]
            session.add(DemoDisposition(disposition_id='DISP-'+str(uuid4()), plan_id=plan_id,
                exception_id=p['exceptionId'], action=p['disposition'], status=state))
        plan.status = 'REJECTED' if decision.review_outcome == 'REJECT' else 'EXECUTED'
        plan.updated_at = utcnow()
        audit(session, plan, 'DEMO_DISPOSITION_REJECTED' if plan.status == 'REJECTED' else 'DEMO_DISPOSITION_EXECUTED',
              {'reviewOutcome':decision.review_outcome,'dispositions':actions,'positionsChanged':False})
    return plan


def read_plan(session, plan):
    decision = session.scalar(select(ReviewDecision).where(ReviewDecision.plan_id == plan.plan_id))
    return dict(contractVersion='1.0', demoOnly=True, identityVerification=LABEL, planId=plan.plan_id,
        transferId=plan.transfer_id, reconciliationRunId=plan.reconciliation_run_id,
        agentInvestigationId=plan.agent_investigation_id, status=plan.status, planVersion=plan.plan_version,
        planHash=plan.plan_hash, proposedActions=plan.proposed_actions, evidenceReferences=plan.evidence_references,
        createdAt=plan.created_at, updatedAt=plan.updated_at, expiresAt=plan.context['hashContent']['expiresAt'],
        investigationSummary=plan.context['investigationSummary'], overallRiskLevel=plan.context['overallRiskLevel'],
        documentEvidenceStatus=plan.context['documentEvidenceStatus'], clientReference=plan.context['clientReference'],
        decision=None if not decision else dict(decisionId=decision.decision_id,reviewOutcome=decision.review_outcome,
            reviewerReference=decision.reviewer_reference,reviewerComments=decision.reviewer_comments,
            additionalInformation=decision.additional_information,reviewEventReference=decision.review_event_reference,
            identityVerification=LABEL,decidedAt=decision.decided_at))


def verify(session, plan):
    run, exceptions = current(session, plan)
    decision = session.scalar(select(ReviewDecision).where(ReviewDecision.plan_id == plan.plan_id))
    actual = session.scalars(select(DemoDisposition).where(DemoDisposition.plan_id == plan.plan_id)).all()
    events = session.scalars(select(AuditEvent).where(AuditEvent.plan_id == plan.plan_id).order_by(AuditEvent.created_at)).all()
    expected = effective_actions(plan, decision) if decision else []
    if expected:
        validate_actions(session, exceptions, expected)
    expected_state = {'ACCEPT_VERIFIED_EXPLANATION':'ACKNOWLEDGED','REQUEST_ADDITIONAL_EVIDENCE':'EVIDENCE_REQUESTED',
        'ESCALATE_TO_TRANSFER_OPERATIONS':'OPEN_ESCALATED','OPEN_COST_BASIS_CASE':'OPEN_BASIS_CASE'}
    matches = sorted((x.exception_id,x.action,x.status) for x in actual) == sorted(
        (x['exceptionId'],x['disposition'],expected_state[x['disposition']]) for x in expected)
    inputs = collect_inputs(session, session.get(Transfer, plan.transfer_id))
    unchanged = inputs['source'] == plan.context['source'] and inputs['target'] == plan.context['target']
    audit_types = {e.action for e in events}
    complete = plan.status in ('EXECUTED','REJECTED') and decision and matches and unchanged and (
        {'PLAN_PREVIEWED','DEMO_REVIEW_RECORDED', 'DEMO_DISPOSITION_REJECTED' if plan.status=='REJECTED' else 'DEMO_DISPOSITION_EXECUTED'} <= audit_types)
    outcome = {'APPROVE':'REVIEWED_WITH_OPEN_EXCEPTIONS','REQUEST_EVIDENCE':'EVIDENCE_REQUESTED',
        'ESCALATE':'ESCALATED','REJECT':'REVIEW_REJECTED'}.get(decision.review_outcome if decision else None, 'REVIEW_FAILED')
    return dict(transferId=plan.transfer_id,reconciliationRunId=run.reconciliation_run_id,
        investigationSummary=plan.context['investigationSummary'],planId=plan.plan_id,planStatus=plan.status,
        humanReviewOutcome=decision.review_outcome if decision else None,evidenceReferences=plan.evidence_references,
        reviewedDispositions=[dict(exceptionId=x.exception_id,disposition=x.action,status=x.status) for x in actual],
        unresolvedExceptions=[ExceptionResponse.model_validate({**snapshot(e), 'normalized_quantity':e.expected_quantity,
            'status':e.resolution_status}).model_dump(mode='json',by_alias=True) for e in exceptions if e.resolution_status!='EXPLAINED'],
        documentEvidenceStatus=plan.context['documentEvidenceStatus'],verificationStatus='VERIFIED_DEMO_STATE' if complete else 'NOT_VERIFIED',
        workflowOutcome=outcome if complete else 'REVIEW_FAILED',auditReference=plan.plan_id,
        auditEventIds=[e.event_id for e in events],positionsUnchanged=unchanged,transferCompleted=False,
        identityVerification=LABEL,demoOnly=True)
