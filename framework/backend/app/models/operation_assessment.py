"""Additive assessment tables; existing manual grades remain authoritative."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class OperationAssessmentConfig(Base):
    __tablename__ = 'operation_assessment_configs'
    version_id: Mapped[int] = mapped_column(ForeignKey('operation_versions.id'), primary_key=True)
    revision: Mapped[int] = mapped_column(default=1)
    content: Mapped[dict] = mapped_column(JSON)


class OperationEvidenceEvent(Base):
    __tablename__ = 'operation_evidence_events'
    __table_args__ = (UniqueConstraint('session_id', 'sequence'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('operation_sessions.id'), index=True)
    sequence: Mapped[int] = mapped_column()
    content: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))


class ExamEvidenceSeal(Base):
    __tablename__ = 'exam_evidence_seals'
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), primary_key=True)
    content: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))


class ExamEvaluation(Base):
    __tablename__ = 'exam_evaluations'
    __table_args__ = (UniqueConstraint('session_id', 'version'), UniqueConstraint('session_id', 'fingerprint'))
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), index=True)
    version: Mapped[int] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)


class ExamAssessmentReview(Base):
    __tablename__ = 'exam_assessment_reviews'
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey('exam_evaluations.id'))
    grade_revision: Mapped[int] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime)


class ExamStudentCommentary(Base):
    __tablename__ = 'exam_student_commentaries'
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40))
    token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    text: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    attempts: Mapped[int] = mapped_column(default=0)


class ExamAssessmentReviewHistory(Base):
    __tablename__ = 'exam_assessment_review_history'
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('exam_attempts.session_id'), index=True)
    content: Mapped[dict] = mapped_column(JSON)


class ExamPublishedAssessment(Base):
    __tablename__ = 'exam_published_assessments'
    publication_id: Mapped[int] = mapped_column(ForeignKey('exam_grade_publications.id'), primary_key=True)
    content: Mapped[dict] = mapped_column(JSON)
