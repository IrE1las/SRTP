"""Exercise session lifecycle service."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.models.operation_log import OperationLog
from app.models.user import User
from app.services.interlocking.seed_service import reset_station_runtime_state, seed_default_station


def utc_now() -> datetime:
    """Return current UTC time."""

    return datetime.utcnow()


def start_session(db: Session, exercise: Exercise, student: User) -> ExerciseSession:
    """Start a new exercise session with a clean station runtime state."""

    seed_default_station(db)
    reset_station_runtime_state(db, exercise.station_id)
    session = ExerciseSession(
        student_id=student.id,
        exercise_id=exercise.id,
        station_id=exercise.station_id,
        start_time=utc_now(),
        status="ongoing",
        result_summary={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: int) -> ExerciseSession | None:
    """Return an exercise session."""

    return db.get(ExerciseSession, session_id)


def get_user_session(db: Session, session_id: int, user: User) -> ExerciseSession | None:
    """Return a session visible to the current user."""

    session = get_session(db, session_id)
    if session is None:
        return None
    if user.role == "student" and session.student_id != user.id:
        return None
    return session


def get_deadline(session: ExerciseSession, exercise: Exercise) -> datetime:
    """Return the session deadline."""

    return session.start_time + timedelta(seconds=exercise.time_limit)


def is_timed_out(session: ExerciseSession, exercise: Exercise) -> bool:
    """Return whether the session has exceeded its time limit."""

    return utc_now() > get_deadline(session, exercise)


def finish_session(
    db: Session,
    session: ExerciseSession,
    status: str,
    completion_status: str,
    final_snapshot: dict | None,
    result_summary: dict,
) -> ExerciseSession:
    """Finish a session and persist summary fields."""

    end_time = utc_now()
    session.status = status
    session.completion_status = completion_status
    session.end_time = end_time
    session.total_time = int((end_time - session.start_time).total_seconds())
    session.final_snapshot = final_snapshot
    session.result_summary = result_summary
    db.commit()
    db.refresh(session)
    return session


def list_history(db: Session, student_id: int) -> list[ExerciseSession]:
    """Return history sessions for a student."""

    return (
        db.query(ExerciseSession)
        .filter(ExerciseSession.student_id == student_id)
        .order_by(ExerciseSession.created_at.desc(), ExerciseSession.id.desc())
        .all()
    )


def list_session_logs(db: Session, session_id: int) -> list[OperationLog]:
    """Return operation logs for a session in replay order."""

    return (
        db.query(OperationLog)
        .filter(OperationLog.session_id == session_id)
        .order_by(OperationLog.sequence_no)
        .all()
    )
