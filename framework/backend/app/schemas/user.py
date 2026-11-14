"""User request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

UserRole = Literal["student", "teacher", "admin"]


class UserBase(BaseModel):
    """Common user fields shared by requests and responses."""

    username: str = Field(min_length=3, max_length=50)
    real_name: str | None = Field(default=None, max_length=50)
    role: UserRole = "student"
    student_id: str | None = Field(default=None, max_length=30)
    class_name: str | None = Field(default=None, max_length=50)


class UserRegister(UserBase):
    """Request body for user registration."""

    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    """Request body for JSON login."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(UserBase):
    """Public user data returned to the frontend."""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
