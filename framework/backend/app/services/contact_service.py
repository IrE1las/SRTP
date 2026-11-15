"""Contact-only verification lock: five failures, persistent until an admin unlocks."""
from fastapi import HTTPException
from sqlalchemy import case, update

from app.core.security import verify_password
from app.models.user import User

LOCK_MESSAGE = "联系方式修改已锁定，请联系管理员解锁"
FAILURE_LIMIT = 5


def update_contacts(db, user, body):
    limited = user.role in ("student", "teacher")
    if limited and user.contact_locked:
        raise HTTPException(403, LOCK_MESSAGE)

    identity = (User.id == user.id, User.token_version == user.token_version, User.is_active.is_(True))
    if not verify_password(body.current_password, user.password_hash):
        if not limited:
            raise HTTPException(400, "当前密码错误，未保存任何变更")
        # Increment in SQL, never from a previously read counter. Concurrent failures cannot be lost.
        result = db.execute(update(User).where(*identity, User.contact_locked.is_(False)).values(
            contact_failures=User.contact_failures + 1,
            contact_locked=case((User.contact_failures >= FAILURE_LIMIT - 1, True), else_=False),
        ), execution_options={"synchronize_session": False})
        db.commit()
        db.refresh(user)
        if user.contact_locked:
            raise HTTPException(403, "当前密码错误，" + LOCK_MESSAGE)
        if result.rowcount != 1:
            raise HTTPException(409, "账号状态已变化，请重新登录后操作")
        raise HTTPException(400, f"当前密码错误，还可尝试{FAILURE_LIMIT - user.contact_failures}次，未保存任何变更")

    values = body.model_dump(exclude={"current_password"}, exclude_unset=True)
    # The lock predicate also protects a correct request racing the fifth failure.
    predicates = (*identity, User.contact_locked.is_(False)) if limited else identity
    result = db.execute(update(User).where(*predicates).values(
        **values, contact_failures=0,
    ), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        db.refresh(user)
        if limited and user.contact_locked:
            raise HTTPException(403, LOCK_MESSAGE)
        raise HTTPException(409, "账号状态已变化，请重新登录后操作")
    db.commit()
    db.refresh(user)
    return user


def unlock_contacts(db, user):
    if user.role not in ("student", "teacher"):
        raise HTTPException(400, "只有学生和教师需要解锁联系方式修改")
    db.execute(update(User).where(User.id == user.id).values(contact_failures=0, contact_locked=False),
               execution_options={"synchronize_session": False})
    db.commit()
    db.refresh(user)
    return user
