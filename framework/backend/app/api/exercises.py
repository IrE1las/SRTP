"""Exercise management and session API routes."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.exercise import (
    ExerciseCreateRequest,
    ExerciseDetailResponse,
    ExerciseLobbyItemResponse,
    ExerciseReplayResponse,
    ExerciseResponse,
    ExerciseSessionFinishRequest,
    ExerciseSessionResponse,
    ExerciseSessionStartRequest,
    ExerciseStartResponse,
    ExerciseUpdateRequest,
    OperationLogResponse,
)
from app.schemas.station import StationDetailResponse
from app.services.ai_scoring.scoring_service import generate_ai_score
from app.services.exercise.exercise_service import (
    create_exercise,
    delete_exercise,
    get_exercise,
    list_lobby_exercises,
    list_teacher_exercises,
    update_exercise,
)
from app.services.exercise.session_service import (
    finish_session,
    get_user_session,
    list_history,
    list_session_logs,
    start_session,
)
from app.services.interlocking.engine import InterlockingEngine
from app.services.interlocking.repository import InterlockingRepository

router = APIRouter()


@router.get("/exercises/teacher", response_model=list[ExerciseResponse])
def list_my_exercises(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
) -> list[ExerciseResponse]:
    """Return exercises created by the current teacher."""

    owner_id = None if current_user.role == "admin" else current_user.id
    return [ExerciseResponse.model_validate(item) for item in list_teacher_exercises(db, owner_id)]


@router.post("/exercises", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
def create_teacher_exercise(
    payload: ExerciseCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
) -> ExerciseResponse:
    """Create an exercise."""

    return ExerciseResponse.model_validate(create_exercise(db, current_user.id, payload))


@router.put("/exercises/{exercise_id}", response_model=ExerciseResponse)
def update_teacher_exercise(
    exercise_id: int,
    payload: ExerciseUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
) -> ExerciseResponse:
    """Update an exercise."""

    exercise = get_exercise(db, exercise_id)
    if exercise is None or (current_user.role == "teacher" and exercise.teacher_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习题不存在")
    return ExerciseResponse.model_validate(update_exercise(db, exercise, payload))


@router.delete("/exercises/{exercise_id}")
def delete_teacher_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
) -> dict[str, str]:
    """Delete an exercise."""

    exercise = get_exercise(db, exercise_id)
    if exercise is None or (current_user.role == "teacher" and exercise.teacher_id != current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习题不存在")
    delete_exercise(db, exercise)
    return {"message": "练习题已删除"}


@router.get("/exercises/lobby", response_model=list[ExerciseLobbyItemResponse])
def list_exercise_lobby(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExerciseLobbyItemResponse]:
    """Return active exercises for students."""

    return [ExerciseLobbyItemResponse.model_validate(item) for item in list_lobby_exercises(db)]


@router.get("/exercises/{exercise_id}", response_model=ExerciseDetailResponse)
def get_exercise_detail(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseDetailResponse:
    """Return one exercise detail."""

    exercise = get_exercise(db, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习题不存在")
    return ExerciseDetailResponse.model_validate(exercise)


@router.post("/exercise-sessions/start", response_model=ExerciseStartResponse)
def start_exercise_session(
    payload: ExerciseSessionStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseStartResponse:
    """Start a student's exercise session."""

    exercise = get_exercise(db, payload.exercise_id)
    if exercise is None or not exercise.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习题不存在或未发布")
    session = start_session(db, exercise, current_user)
    repository = InterlockingRepository(db, session.station_id)
    station_detail = StationDetailResponse.model_validate(repository.get_station_detail())
    snapshot = InterlockingEngine(db, session.station_id).get_station_snapshot()
    return ExerciseStartResponse(
        exercise=ExerciseDetailResponse.model_validate(exercise),
        session=ExerciseSessionResponse.model_validate(session),
        station_detail=station_detail,
        snapshot=snapshot,
        deadline_at=session.start_time + timedelta(seconds=exercise.time_limit),
    )


@router.post("/exercise-sessions/{session_id}/finish", response_model=ExerciseSessionResponse)
def finish_exercise_session(
    session_id: int,
    payload: ExerciseSessionFinishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseSessionResponse:
    """Manually finish a session."""

    session = get_user_session(db, session_id, current_user)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习会话不存在")
    snapshot = InterlockingEngine(db, session.station_id).get_station_snapshot().model_dump(mode="json")
    status_value = "timeout" if payload.reason == "timeout" else "aborted"
    completion_value = "timeout" if payload.reason == "timeout" else "failed"
    finished = finish_session(
        db,
        session,
        status=status_value,
        completion_status=completion_value,
        final_snapshot=snapshot,
        result_summary={"message": payload.reason, "target_completed": False},
    )
    generate_ai_score(db, finished.id)
    return ExerciseSessionResponse.model_validate(finished)


@router.get("/exercise-sessions/history", response_model=list[ExerciseSessionResponse])
def get_exercise_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExerciseSessionResponse]:
    """Return current user's exercise history."""

    return [ExerciseSessionResponse.model_validate(item) for item in list_history(db, current_user.id)]


@router.get("/exercise-sessions/{session_id}/replay", response_model=ExerciseReplayResponse)
def get_exercise_replay(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseReplayResponse:
    """Return operation logs for replay."""

    session = get_user_session(db, session_id, current_user)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习会话不存在")
    exercise = get_exercise(db, session.exercise_id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习题不存在")
    return ExerciseReplayResponse(
        session=ExerciseSessionResponse.model_validate(session),
        exercise=ExerciseDetailResponse.model_validate(exercise),
        logs=[OperationLogResponse.model_validate(item) for item in list_session_logs(db, session_id)],
    )
