"""Operation log service."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.exercise_session import ExerciseSession
from app.models.operation_log import OperationLog


def append_operation_log(
    db: Session,
    session: ExerciseSession,
    operation_type: str,
    target_code: str,
    target_type: str,
    operation_result: str,
    request_payload: dict,
    state_before: dict,
    state_after: dict,
    error_message: str | None,
    time_spent_ms: int,
) -> OperationLog:
    """Append one operation log and update session click counters."""

    max_sequence = (
        db.query(func.max(OperationLog.sequence_no))
        .filter(OperationLog.session_id == session.id)
        .scalar()
        or 0
    )
    log = OperationLog(
        session_id=session.id,
        sequence_no=max_sequence + 1,
        operation_type=operation_type,
        target_code=target_code,
        target_type=target_type,
        operation_result=operation_result,
        request_payload=request_payload,
        state_before=state_before,
        state_after=state_after,
        error_message=error_message,
        time_spent_ms=time_spent_ms,
    )
    db.add(log)
    session.total_clicks += 1
    if operation_result == "success":
        session.valid_clicks += 1
    else:
        session.invalid_clicks += 1
    db.flush()
    return log
