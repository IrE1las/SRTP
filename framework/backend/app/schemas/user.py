"""Explicit account and profile contracts; credential fields are request-only."""
from datetime import datetime
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

UserRole = Literal["student", "teacher", "admin"]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    real_name: str | None = Field(default=None, max_length=50)
    role: UserRole = "student"
    student_id: str | None = Field(default=None, max_length=30)
    class_name: str | None = Field(default=None, max_length=50)


class UserRegister(UserBase):
    """Internal compatibility contract; public registration is disabled."""
    password: str = Field(min_length=1, max_length=1024, repr=False)


class UserLogin(StrictRequest):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class ContactUpdate(StrictRequest):
    current_password: str = Field(min_length=1, max_length=1024, repr=False)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("email", "phone", mode="before")
    @classmethod
    def empty_as_null(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        if value is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("电子邮箱格式不正确")
        return value

    @field_validator("phone")
    @classmethod
    def phone_format(cls, value):
        if value is not None and not re.fullmatch(r"\+?[0-9][0-9 ()-]{4,30}[0-9]", value):
            raise ValueError("手机号格式不正确")
        return value


class PasswordChange(StrictRequest):
    current_password: str = Field(min_length=1, max_length=1024, repr=False)
    new_password: str = Field(min_length=1, max_length=1024, repr=False)
    confirm_password: str = Field(min_length=1, max_length=1024, repr=False)


class PasswordReset(StrictRequest):
    new_password: str = Field(min_length=1, max_length=1024, repr=False)


class UserResponse(UserBase):
    id: int
    email: str | None = None
    phone: str | None = None
    contact_failures: int = 0
    contact_locked: bool = False
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator("real_name", "student_id", "class_name", "email", "phone", mode="before")
    @classmethod
    def missing_as_null(cls, value):
        return None if isinstance(value, str) and not value.strip() else value
