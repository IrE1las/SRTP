"""Frozen exam eligibility and durable attempts. S5 deliberately has no grade model."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Exam(Base):
    __tablename__ = 'exams'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    publisher_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    revision: Mapped[int] = mapped_column(default=1)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classes: Mapped[list] = mapped_column(JSON, default=list)
    version_id: Mapped[int | None] = mapped_column(ForeignKey('operation_versions.id'), nullable=True)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    question_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExamParticipant(Base):
    __tablename__ = 'exam_participants'
    exam_id: Mapped[int] = mapped_column(ForeignKey('exams.id'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    identity_snapshot: Mapped[dict] = mapped_column(JSON)


class ExamAttempt(Base):
    __tablename__ = 'exam_attempts'
    __table_args__ = (UniqueConstraint('exam_id', 'student_id'),)
    session_id: Mapped[str] = mapped_column(ForeignKey('operation_sessions.id'), primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey('exams.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    deadline: Mapped[datetime] = mapped_column(DateTime, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    exit_count: Mapped[int] = mapped_column(default=0)
    fullscreen_state: Mapped[str] = mapped_column(String(20), default='inside')
    exited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_control_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revision: Mapped[int] = mapped_column(default=0)


class ExamControlEvent(Base):
    __tablename__ = 'exam_control_events'
    __table_args__ = (UniqueConstraint('session_id', 'event_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
