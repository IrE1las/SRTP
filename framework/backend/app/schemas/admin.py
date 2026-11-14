"""Admin schemas."""

from pydantic import BaseModel, ConfigDict, Field


class AdminUserResponse(BaseModel):
    """User row for admin management."""

    id: int
    username: str
    real_name: str | None
    role: str
    student_id: str | None
    class_name: str | None

    model_config = ConfigDict(from_attributes=True)


class AdminUserUpdateRequest(BaseModel):
    """Admin user update request."""

    real_name: str | None = Field(default=None, max_length=50)
    role: str | None = Field(default=None, max_length=20)
    student_id: str | None = Field(default=None, max_length=30)
    class_name: str | None = Field(default=None, max_length=50)


class AdminOverviewResponse(BaseModel):
    """System overview for admins."""

    user_count: int
    exercise_count: int
    session_count: int
    operation_log_count: int
