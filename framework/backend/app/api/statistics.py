"""Statistics API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.user import User
from app.services.statistics_service import student_statistics, teacher_statistics

router = APIRouter()


@router.get("/student/me")
def get_my_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's learning statistics."""

    return student_statistics(db, current_user.id)


@router.get("/teacher/overview")
def get_teacher_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
) -> dict:
    """Return teacher exercise statistics."""

    return teacher_statistics(db, None if current_user.role == "admin" else current_user.id)
