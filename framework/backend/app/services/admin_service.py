"""Admin management service."""

from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.models.operation_log import OperationLog
from app.models.user import User
from app.schemas.admin import AdminUserUpdateRequest


def get_overview(db: Session) -> dict[str, int]:
    """Return system overview counts."""

    return {
        "user_count": db.query(User).count(),
        "exercise_count": db.query(Exercise).count(),
        "session_count": db.query(ExerciseSession).count(),
        "operation_log_count": db.query(OperationLog).count(),
    }


def list_users(db: Session) -> list[User]:
    """Return all users."""

    return db.query(User).order_by(User.id).all()


def update_user(db: Session, user: User, payload: AdminUserUpdateRequest) -> User:
    """Update user profile and role."""

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    """Delete a user."""

    db.delete(user)
    db.commit()
