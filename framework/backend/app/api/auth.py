"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.token import TokenResponse
from app.schemas.user import UserLogin, UserRegister, UserResponse
from app.services.user_service import (
    authenticate_user,
    create_user,
    get_user_by_username,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)) -> User:
    """Register a student or teacher; administrators are managed privately."""

    if user_in.role == "admin":
        raise HTTPException(status_code=403, detail="管理员账户不能通过公开注册创建")

    existing_user = get_user_by_username(db, user_in.username)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在",
        )
    return create_user(db, user_in)


@router.post("/login", response_model=TokenResponse)
def login(login_in: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and issue a JWT access token."""

    user = authenticate_user(db, login_in.username, login_in.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
    )
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the current authenticated user."""

    return current_user
