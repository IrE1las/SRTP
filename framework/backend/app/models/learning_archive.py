"""New console and classic evidence, independent of existing teaching records."""
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class LearningArchive(Base):
    __tablename__ = 'learning_archives'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(String(30))
    preview: Mapped[bool] = mapped_column(default=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    initial_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    latest_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    feedback: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LearningArchiveEvent(Base):
    __tablename__ = 'learning_archive_events'
    __table_args__ = (UniqueConstraint('archive_id', 'sequence'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    archive_id: Mapped[str] = mapped_column(ForeignKey('learning_archives.id'), index=True)
    sequence: Mapped[int] = mapped_column()
    command: Mapped[dict[str, Any]] = mapped_column(JSON)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    before_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
