"""AI score schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class WrongOperation(BaseModel):
    """Wrong or failed operation summary."""

    sequence_no: int
    operation: str
    target: str
    error: str | None = None


class AiScoreResponse(BaseModel):
    """AI score response."""

    id: int
    session_id: int
    accuracy_score: float
    efficiency_score: float
    operation_quality: float
    total_score: float
    ai_comment: str
    wrong_operations: list[dict[str, Any]]
    suggestions: list[str]
    deepseek_response: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiScoreSummaryResponse(BaseModel):
    """Compact score summary."""

    session_id: int
    total_score: float
    ai_comment: str
