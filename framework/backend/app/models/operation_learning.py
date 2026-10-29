"""Learning submissions and shared reviews, separate from theory and exams."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class OperationAttempt(Base):
    __tablename__ = 'operation_attempts'
    session_id: Mapped[str] = mapped_column(ForeignKey('operation_sessions.id'), primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('operation_questions.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    # NULL after sealing; a unique key arbitrates starts across processes.
    active_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    previous_session_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    question_snapshot: Mapped[dict] = mapped_column(JSON)
    identity_snapshot: Mapped[dict] = mapped_column(JSON)
    outcome: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_status: Mapped[str] = mapped_column(String(30), default='not_requested')
    ai_text: Mapped[str | None] = mapped_column(String(16000), nullable=True)
    ai_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ai_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OperationReview(Base):
    __tablename__ = 'operation_reviews'
    session_id: Mapped[str] = mapped_column(ForeignKey('operation_attempts.session_id'), primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)
    comment: Mapped[str | None] = mapped_column(String(6000), nullable=True)
    confirmed: Mapped[bool] = mapped_column(default=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    audit: Mapped[list] = mapped_column(JSON, default=list)
