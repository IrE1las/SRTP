"""Exercise completion rules."""

from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.services.ai_scoring.scoring_service import generate_ai_score
from app.services.exercise.session_service import finish_session, is_timed_out


def maybe_finish_by_completion(db, session: ExerciseSession, exercise: Exercise, snapshot: dict) -> ExerciseSession:
    """Finish a session when target routes are established or time has expired."""

    if session.status != "ongoing":
        return session

    if is_timed_out(session, exercise):
        finished = finish_session(
            db,
            session,
            status="timeout",
            completion_status="timeout",
            final_snapshot=snapshot,
            result_summary={"message": "练习超时", "target_completed": False},
        )
        generate_ai_score(db, finished.id)
        return finished

    if _target_routes_completed(exercise, snapshot):
        finished = finish_session(
            db,
            session,
            status="completed",
            completion_status="success",
            final_snapshot=snapshot,
            result_summary={"message": "目标进路办理完成", "target_completed": True},
        )
        generate_ai_score(db, finished.id)
        return finished
    return session


def _target_routes_completed(exercise: Exercise, snapshot: dict) -> bool:
    targets = exercise.target_routes or []
    active_routes = snapshot.get("active_routes", [])
    for target in targets:
        matched = any(
            route.get("entry_signal") == target.get("entry_signal")
            and route.get("exit_signal") == target.get("exit_signal")
            and route.get("status") == "locked"
            and route.get("opened_signal") == target.get("entry_signal")
            for route in active_routes
        )
        if not matched:
            return False
    return bool(targets)
