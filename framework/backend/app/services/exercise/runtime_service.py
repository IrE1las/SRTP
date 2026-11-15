"""Session-scoped interlocking runtime service with operation logging."""

from time import perf_counter
from typing import Callable

from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.models.user import User
from app.schemas.exercise import ExerciseRuntimeResponse
from app.schemas.interlocking import InterlockingActionResponse
from app.services.exercise.completion_service import maybe_finish_by_completion
from app.services.exercise.logging_service import append_operation_log
from app.services.exercise.session_service import finish_session, get_user_session, is_timed_out
from app.services.interlocking.engine import InterlockingEngine


class ExerciseRuntimeError(ValueError):
    """Raised when a session-scoped runtime operation is invalid."""


def run_interlocking_operation(
    db: Session,
    user: User,
    session_id: int,
    operation_type: str,
    target_code: str,
    target_type: str,
    request_payload: dict,
    operation: Callable[[InterlockingEngine], InterlockingActionResponse],
) -> ExerciseRuntimeResponse:
    """Run one interlocking operation inside an exercise session and log it."""

    session = get_user_session(db, session_id, user)
    if session is None:
        raise ExerciseRuntimeError("练习会话不存在")
    exercise = db.get(Exercise, session.exercise_id)
    if exercise is None:
        raise ExerciseRuntimeError("练习题不存在")
    if session.status != "ongoing":
        raise ExerciseRuntimeError("练习会话已结束")

    engine = InterlockingEngine(db, session.station_id)
    before = engine.get_station_snapshot().model_dump(mode="json")

    if is_timed_out(session, exercise):
        session = finish_session(
            db,
            session,
            status="timeout",
            completion_status="timeout",
            final_snapshot=before,
            result_summary={"message": "练习超时", "target_completed": False},
        )
        append_operation_log(
            db,
            session,
            operation_type="timeout_auto_finish",
            target_code="timeout",
            target_type="session",
            operation_result="timeout_auto_finish",
            request_payload={},
            state_before=before,
            state_after=before,
            error_message="练习超时",
            time_spent_ms=0,
        )
        db.commit()
        return ExerciseRuntimeResponse(success=False, message="练习超时", snapshot=engine.get_station_snapshot(), session=session)

    start = perf_counter()
    error_message: str | None = None
    try:
        response = operation(engine)
        success = response.success
        message = response.message
        if not success:
            error_message = message
        after = response.snapshot.model_dump(mode="json")
    except Exception as exc:
        success = False
        message = str(exc)
        error_message = message
        after = engine.get_station_snapshot().model_dump(mode="json")

    elapsed_ms = int((perf_counter() - start) * 1000)
    append_operation_log(
        db,
        session,
        operation_type=operation_type,
        target_code=target_code,
        target_type=target_type,
        operation_result="success" if success else "failed",
        request_payload=request_payload,
        state_before=before,
        state_after=after,
        error_message=error_message if not success else None,
        time_spent_ms=elapsed_ms,
    )
    session = maybe_finish_by_completion(db, session, exercise, after)
    db.commit()
    db.refresh(session)
    return ExerciseRuntimeResponse(
        success=success,
        message=message,
        snapshot=engine.get_station_snapshot(),
        session=session,
    )
