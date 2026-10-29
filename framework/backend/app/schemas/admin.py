"""Administrator-only account requests and public responses."""
from pydantic import Field, field_validator
from app.schemas.user import StrictRequest, UserResponse, UserRole


class AdminUserResponse(UserResponse):
    pass


class IdentityFields(StrictRequest):
    real_name: str | None = Field(default=None, max_length=50)
    student_id: str | None = Field(default=None, max_length=30)
    class_name: str | None = Field(default=None, max_length=50)

    @field_validator("real_name", "student_id", "class_name", mode="before")
    @classmethod
    def normalize_identity(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value


class AdminUserCreateRequest(IdentityFields):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=1024, repr=False)
    role: UserRole = "student"

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, value):
        if value != value.strip() or not value.strip():
            raise ValueError("用户名不能包含首尾空白")
        return value


class AdminUserUpdateRequest(IdentityFields):
    role: UserRole | None = None
    is_active: bool | None = None


class AdminOverviewResponse(StrictRequest):
    user_count: int
    theory_question_count: int
    theory_attempt_count: int
