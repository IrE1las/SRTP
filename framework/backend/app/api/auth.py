"""Authentication and self-service account routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.token import TokenResponse
from app.schemas.user import ContactUpdate, PasswordChange, UserLogin, UserResponse
from app.services.user_service import authenticate_user
from app.services.contact_service import update_contacts

router = APIRouter()


@router.post("/register")
def register():
    raise HTTPException(403, "公开注册已关闭，请联系管理员建立账号")


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.username, body.password)
    if user is None:
        raise HTTPException(401, "用户名或密码错误，或账号已停用", headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token({"sub": str(user.id), "ver": user.token_version})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def read_current_user(user: User = Depends(get_current_user)):
    return user


def check_current_password(user, password):
    # A wrong form password is not an expired login: keep the current session.
    if not verify_password(password, user.password_hash):
        raise HTTPException(400, "当前密码错误，未保存任何变更")


def update_own_account(db, user, values):
    """Compare credential version to reject concurrent reset/disable changes."""
    result = db.execute(update(User).where(
        User.id == user.id, User.token_version == user.token_version, User.is_active.is_(True)
    ).values(**values), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "账号状态已变化，请重新登录后操作")
    db.commit()
    db.refresh(user)


@router.put("/me/contact", response_model=UserResponse)
def update_contact(body: ContactUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return update_contacts(db, user, body)


@router.post("/me/password")
def change_password(body: PasswordChange, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_current_password(user, body.current_password)
    if body.new_password != body.confirm_password:
        raise HTTPException(400, "两次新密码不一致，未保存任何变更")
    update_own_account(db, user, {"password_hash": get_password_hash(body.new_password),
                                "token_version": User.token_version + 1})
    return {"message": "密码已修改，请重新登录"}
