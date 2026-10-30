"""Manual exam drafts and immutable published versions; no automatic evaluation."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ExamGrade(Base):
    __tablename__ = 'exam_grades'
    __table_args__ = (CheckConstraint('score_cents IS NULL OR (score_cents >= 0 AND score_cents <= 10000)'),)
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), primary_key=True)
    revision: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    score_cents: Mapped[int | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    editor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExamGradePublication(Base):
    __tablename__ = 'exam_grade_publications'
    __table_args__ = (UniqueConstraint('session_id', 'version'), UniqueConstraint('session_id', 'source_revision'),
                      CheckConstraint('score_cents >= 0 AND score_cents <= 10000'))
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), index=True)
    version: Mapped[int] = mapped_column()
    source_revision: Mapped[int] = mapped_column()
    score_cents: Mapped[int] = mapped_column()
    comment: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    publisher_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    published_at: Mapped[datetime] = mapped_column(DateTime)


class ExamGradeAudit(Base):
    __tablename__ = 'exam_grade_audits'
    __table_args__ = (UniqueConstraint('session_id', 'revision'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), index=True)
    revision: Mapped[int] = mapped_column()
    action: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    snapshot: Mapped[dict] = mapped_column(JSON)
