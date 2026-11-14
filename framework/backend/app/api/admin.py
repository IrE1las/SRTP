"""Admin API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import AdminOverviewResponse, AdminUserResponse, AdminUserUpdateRequest
from app.services.admin_service import delete_user, get_overview, list_users, update_user

router = APIRouter()


@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> AdminOverviewResponse:
    """Return admin overview."""

    return AdminOverviewResponse(**get_overview(db))


@router.get("/users", response_model=list[AdminUserResponse])
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> list[AdminUserResponse]:
    """Return all users."""

    return [AdminUserResponse.model_validate(user) for user in list_users(db)]


@router.put("/users/{user_id}", response_model=AdminUserResponse)
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> AdminUserResponse:
    """Update a user."""

    if user_id == current_user.id and payload.role not in (None, "admin"):
        raise HTTPException(status_code=400, detail="不能取消当前账户的管理员权限")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return AdminUserResponse.model_validate(update_user(db, user, payload))


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> dict[str, str]:
    """Delete a user."""

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前管理员账号")
    delete_user(db, user)
    return {"message": "用户已删除"}
