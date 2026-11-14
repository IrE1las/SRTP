"""Statistics service."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai_score import AiScore
from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.models.operation_log import OperationLog
from app.models.user import User


def student_statistics(db: Session, student_id: int) -> dict:
    """Return personal student statistics."""

    sessions = db.query(ExerciseSession).filter(ExerciseSession.student_id == student_id).all()
    session_ids = [session.id for session in sessions]
    scores = db.query(AiScore).filter(AiScore.session_id.in_(session_ids)).all() if session_ids else []
    completed = [session for session in sessions if session.status == "completed"]
    average_score = round(sum(score.total_score for score in scores) / len(scores), 2) if scores else 0
    wrong_count = (
        db.query(OperationLog)
        .filter(OperationLog.session_id.in_(session_ids), OperationLog.operation_result != "success")
        .count()
        if session_ids
        else 0
    )
    return {
        "total_sessions": len(sessions),
        "completed_sessions": len(completed),
        "average_score": average_score,
        "wrong_operation_count": wrong_count,
        "recent_scores": [
            {"session_id": score.session_id, "total_score": score.total_score, "created_at": score.created_at}
            for score in scores[-10:]
        ],
    }


def teacher_statistics(db: Session, teacher_id: int | None) -> dict:
    """Return teacher overview statistics."""

    query = db.query(Exercise)
    if teacher_id is not None:
        query = query.filter(Exercise.teacher_id == teacher_id)
    exercises = query.all()
    exercise_ids = [exercise.id for exercise in exercises]
    sessions = db.query(ExerciseSession).filter(ExerciseSession.exercise_id.in_(exercise_ids)).all() if exercise_ids else []
    session_ids = [session.id for session in sessions]
    scores = db.query(AiScore).filter(AiScore.session_id.in_(session_ids)).all() if session_ids else []
    completed_count = len([session for session in sessions if session.status == "completed"])
    average_score = round(sum(score.total_score for score in scores) / len(scores), 2) if scores else 0
    return {
        "exercise_count": len(exercises),
        "session_count": len(sessions),
        "completed_count": completed_count,
        "completion_rate": round(completed_count / len(sessions) * 100, 2) if sessions else 0,
        "average_score": average_score,
    }
