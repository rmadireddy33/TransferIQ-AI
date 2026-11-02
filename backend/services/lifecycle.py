from backend.models.entities import TransferStatus as S

# Valid state edges only; no status-changing HTTP endpoint is exposed in Step 2.
TRANSITIONS = {
    S.DRAFT: {S.SUBMITTED},
    S.SUBMITTED: {S.UNDER_REVIEW},
    S.UNDER_REVIEW: {S.EXCEPTION_DETECTED, S.RESOLVED, S.ESCALATED},
    S.EXCEPTION_DETECTED: {S.INVESTIGATING, S.ESCALATED},
    S.INVESTIGATING: {S.PENDING_APPROVAL, S.RESOLVED, S.ESCALATED},
    S.PENDING_APPROVAL: {S.RESOLVED, S.ESCALATED},
    S.RESOLVED: {S.COMPLETED},
    S.ESCALATED: {S.UNDER_REVIEW},
    S.COMPLETED: set(),
}


def validate_transition(current: S, target: S) -> None:
    if target not in TRANSITIONS[current]:
        raise ValueError(f"Invalid transfer transition: {current} -> {target}")
