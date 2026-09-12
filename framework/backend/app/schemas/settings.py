"""System settings schemas (AI model configuration)."""

from pydantic import BaseModel


class AISettingsOut(BaseModel):
    """Current AI configuration with the API key masked."""

    api_key_masked: str
    model: str
    base_url: str


class AISettingsUpdate(BaseModel):
    """AI configuration update. Omit api_key to keep the current key."""

    api_key: str | None = None
    model: str
    base_url: str


class AITestRequest(BaseModel):
    """Connection test payload."""

    model: str
    base_url: str
