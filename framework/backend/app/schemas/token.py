"""Authentication token schemas."""

from pydantic import BaseModel

from app.schemas.user import UserResponse


class TokenResponse(BaseModel):
    """JWT login response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
