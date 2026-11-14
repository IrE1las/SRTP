"""AI score ORM model."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiScore(Base):
    """AI or local-rule score for an exercise session."""

    __tablename__ = "ai_scores"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("exercise_sessions.id"), unique=True, index=True, nullable=False)
    accuracy_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    efficiency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    operation_quality: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ai_comment: Mapped[str] = mapped_column(Text, nullable=False)
    wrong_operations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    suggestions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    deepseek_response: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
