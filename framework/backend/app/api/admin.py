"""Administrator-only account API; deletion is replaced by recoverable deactivation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import AdminOverviewResponse, AdminUserCreateRequest, AdminUserResponse, AdminUserUpdateRequest
from app.schemas.user import PasswordReset
from app.services.admin_service import create_account, deactivate_user, get_overview, list_users, reset_password, update_user
from app.services.contact_service import unlock_contacts

router = APIRouter()
admin = require_roles("admin")


def find_user(db, user_id):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    return user


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(db: Session = Depends(get_db), current: User = Depends(admin)):
    return get_overview(db)


@router.get("/users", response_model=list[AdminUserResponse])
def admin_list_users(db: Session = Depends(get_db), current: User = Depends(admin)):
    return list_users(db)


@router.post("/users", response_model=AdminUserResponse, status_code=201)
def admin_create_user(body: AdminUserCreateRequest, db: Session = Depends(get_db), current: User = Depends(admin)):
    return create_account(db, body)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
def admin_update_user(user_id: int, body: AdminUserUpdateRequest, db: Session = Depends(get_db), current: User = Depends(admin)):
    if user_id == current.id and (body.role not in (None, "admin") or body.is_active is False):
        raise HTTPException(400, "不能取消当前账户的管理员权限或停用自己")
    return update_user(db, find_user(db, user_id), body)


@router.post("/users/{user_id}/reset-password", response_model=AdminUserResponse)
def admin_reset_password(user_id: int, body: PasswordReset, db: Session = Depends(get_db), current: User = Depends(admin)):
    target = find_user(db, user_id)
    if target.role == "admin":
        raise HTTPException(400, "管理员请在首页使用当前密码修改自己的密码")
    return reset_password(db, target, body.new_password)


@router.delete("/users/{user_id}")
def admin_deactivate_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(admin)):
    if user_id == current.id:
        raise HTTPException(400, "不能停用当前登录的管理员")
    deactivate_user(db, find_user(db, user_id))
    return {"message": "账号已停用，历史记录保留"}


@router.post("/users/{user_id}/unlock-contact", response_model=AdminUserResponse)
def admin_unlock_contact(user_id: int, db: Session = Depends(get_db), current: User = Depends(admin)):
    return unlock_contacts(db, find_user(db, user_id))
