"""Chapter practice history and bookmarks, separate from examination results."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class PracticeAttempt(Base):
    __tablename__ = 'chapter_practice_attempts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    private_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    answer: Mapped[object | None] = mapped_column(JSON, nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PracticeBookmark(Base):
    __tablename__ = 'chapter_practice_bookmarks'
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
