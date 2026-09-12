"""Report-aligned lessons and durable, separately reviewed student submissions."""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LabQuestion(Base):
    __tablename__ = 'lab_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('shunting_datasets.id'), nullable=False)
    topic: Mapped[int] = mapped_column(nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LabAttempt(Base):
    __tablename__ = 'lab_attempts'
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('lab_questions.id'), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    # Keep the exact rubric/version used when submitted, even after a future import.
    question_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    review: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
