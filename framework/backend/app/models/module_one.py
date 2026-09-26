"""Durable dynamic attempts, separate from static LabAttempt answers."""
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ModuleOneAttempt(Base):
    __tablename__ = "module_one_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(String(60), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    preview: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    version: Mapped[int] = mapped_column(default=0)
    question_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[dict[str, Any]] = mapped_column(JSON)
    initial_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(String(6000), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModuleOneEvent(Base):
    __tablename__ = "module_one_events"
    __table_args__ = (UniqueConstraint("attempt_id", "command_id"), UniqueConstraint("attempt_id", "after_version"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("module_one_attempts.id"), index=True)
    command_id: Mapped[str] = mapped_column(String(36))
    after_version: Mapped[int] = mapped_column()
    command: Mapped[dict[str, Any]] = mapped_column(JSON)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
