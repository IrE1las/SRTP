"""Operation authoring is separate from retained theory answers and future exams."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class OperationQuestion(Base):
    __tablename__ = 'operation_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    published_version: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OperationVersion(Base):
    __tablename__ = 'operation_versions'
    __table_args__ = (UniqueConstraint('question_id', 'number'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('operation_questions.id'), index=True)
    number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default='draft')
    revision: Mapped[int] = mapped_column(default=1)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt: Mapped[str | None] = mapped_column(String(20000), nullable=True)
    classes: Mapped[list] = mapped_column(JSON, default=list)
    initial: Mapped[dict] = mapped_column(JSON, default=dict)
    station_version: Mapped[str] = mapped_column(String(64))
    standard_log: Mapped[list | None] = mapped_column(JSON, nullable=True)
    standard_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OperationSession(Base):
    __tablename__ = 'operation_sessions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey('operation_versions.id'), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default='active')
    revision: Mapped[int] = mapped_column(default=0)
    state_revision: Mapped[int] = mapped_column(default=0)
    engine_state: Mapped[dict] = mapped_column(JSON)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    initial_snapshot: Mapped[dict] = mapped_column(JSON)
    station_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OperationEvent(Base):
    __tablename__ = 'operation_events'
    __table_args__ = (UniqueConstraint('session_id', 'event_id'), UniqueConstraint('session_id', 'sequence'))
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('operation_sessions.id'), index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    sequence: Mapped[int] = mapped_column()
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
