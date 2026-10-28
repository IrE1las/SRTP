"""Account management: stable IDs, unique student numbers and revocable access."""
from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
<<<<<<< Updated upstream

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

=======
from app.core.security import get_password_hash
from app.models.user import User
from app.models.lab_topic import LabQuestion, LabAttempt


def get_overview(db):
    return {"user_count": db.query(User).count(), "theory_question_count": db.query(LabQuestion).count(),
            "theory_attempt_count": db.query(LabAttempt).count()}


def list_users(db):
>>>>>>> Stashed changes
    return db.query(User).order_by(User.id).all()


def commit_account(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "用户名或学号已存在，未保存任何变更") from None


def execute_account_update(db, statement):
    try:
        db.execute(statement, execution_options={"synchronize_session": False})
        commit_account(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "用户名或学号已存在，未保存任何变更") from None


def check_student_number(db, student_id, excluding=None):
    if student_id is not None:
        query = db.query(User).filter(func.trim(User.student_id) == student_id)
        if excluding is not None:
            query = query.filter(User.id != excluding)
        if query.first() is not None:
            raise HTTPException(409, "学号已存在，未保存任何变更")


def create_account(db, payload):
    if payload.role not in ("student", "teacher"):
        raise HTTPException(422, "只能创建学生或教师账号")
    if payload.role == "student" and not all((payload.real_name, payload.student_id, payload.class_name)):
        raise HTTPException(422, "新学生必须填写姓名、学号和班级")
    check_student_number(db, payload.student_id)
    user = User(**payload.model_dump(exclude={"password"}), password_hash=get_password_hash(payload.password))
    db.add(user)
    commit_account(db)
    db.refresh(user)
    return user


def update_user(db: Session, user: User, payload):
    values = payload.model_dump(exclude_unset=True)
    if any(key in values and values[key] is None for key in ("role", "is_active")):
        raise HTTPException(422, "角色和账号状态不能为空")
    if "student_id" in values:
        check_student_number(db, values["student_id"], user.id)
    if values.get("role", user.role) == "student":
        # Legacy missing fields may stay null; do not erase already bound identity.
        for key in ("real_name", "student_id", "class_name"):
            if key in values and values[key] is None and getattr(user, key):
                raise HTTPException(422, "已绑定的学生姓名、学号和班级不能清空")
        if user.role != "student" and not all(values.get(k, getattr(user, k)) for k in
                                              ("real_name", "student_id", "class_name")):
            raise HTTPException(422, "转为学生必须填写姓名、学号和班级")
    if any(key in values and values[key] != getattr(user, key) for key in ("role", "is_active")):
        values["token_version"] = User.token_version + 1
    if values:
        execute_account_update(db, update(User).where(User.id == user.id).values(**values))
    db.refresh(user)
    return user

<<<<<<< Updated upstream
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
=======

def reset_password(db, user, password):
    execute_account_update(db, update(User).where(User.id == user.id).values(
        password_hash=get_password_hash(password), token_version=User.token_version + 1))
    db.refresh(user)
    return user


def deactivate_user(db, user):
    # Keep all teaching links and identity snapshots, including for accounts without submissions.
    execute_account_update(db, update(User).where(User.id == user.id).values(
        is_active=False, token_version=User.token_version + 1))
>>>>>>> Stashed changes
