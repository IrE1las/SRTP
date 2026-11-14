"""AI score API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.exercise_session import ExerciseSession
from app.models.user import User
from app.schemas.ai_score import AiScoreResponse
from app.services.ai_scoring.scoring_service import generate_ai_score, get_ai_score, list_user_scores

router = APIRouter()


def _check_session_visible(db: Session, session_id: int, user: User) -> ExerciseSession:
    session = db.get(ExerciseSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习会话不存在")
    if user.role == "student" and session.student_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该评分")
    return session


@router.post("/sessions/{session_id}/generate", response_model=AiScoreResponse)
def generate_session_score(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AiScoreResponse:
    """Generate score for a finished exercise session."""

    _check_session_visible(db, session_id, current_user)
    try:
        return AiScoreResponse.model_validate(generate_ai_score(db, session_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/sessions/{session_id}", response_model=AiScoreResponse)
def get_session_score(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AiScoreResponse:
    """Return score for a session."""

    _check_session_visible(db, session_id, current_user)
    score = get_ai_score(db, session_id)
    if score is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评分结果不存在")
    return AiScoreResponse.model_validate(score)


@router.get("/me", response_model=list[AiScoreResponse])
def list_my_scores(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AiScoreResponse]:
    """Return scores for the current student."""

    return [AiScoreResponse.model_validate(item) for item in list_user_scores(db, current_user.id)]
