"""Admin management service."""

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.lab_topic import LabQuestion, LabAttempt
from app.models.authoring import GradeAudit, GradeDraft, QuestionRevision, QuestionWorkspace, FeedbackSnippet
from fastapi import HTTPException
from app.schemas.admin import AdminUserUpdateRequest


def get_overview(db: Session) -> dict[str, int]:
    """Return system overview counts."""

    return {
        'user_count': db.query(User).count(),
        'theory_question_count': db.query(LabQuestion).count(),
        'theory_attempt_count': db.query(LabAttempt).count(),
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

    linked = (db.query(LabAttempt).filter((LabAttempt.student_id == user.id) | (LabAttempt.reviewer_id == user.id)).first()
              or db.query(GradeAudit).filter_by(reviewer_id=user.id).first()
              or db.query(GradeDraft).filter_by(reviewer_id=user.id).first()
              or db.query(QuestionRevision).filter_by(author_id=user.id).first()
              or db.query(QuestionWorkspace).filter_by(updated_by=user.id).first()
              or db.query(FeedbackSnippet).filter_by(owner_id=user.id).first())
    if linked:
        raise HTTPException(409, '账号有关联教学记录，不能直接删除；停用功能在S2实现')
    db.delete(user)
    db.commit()
