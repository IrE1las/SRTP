"""Editorial drafts, immutable publication history and grading records."""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class QuestionWorkspace(Base):
    __tablename__='question_workspaces'
    question_id: Mapped[int]=mapped_column(ForeignKey('lab_questions.id'),primary_key=True)
    status: Mapped[str]=mapped_column(String(20),default='published',index=True)
    draft: Mapped[dict[str,Any]|None]=mapped_column(JSON,nullable=True)
    revision: Mapped[int]=mapped_column(default=1)
    published_version: Mapped[int]=mapped_column(default=1)
    updated_by: Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),onupdate=func.now())


class QuestionRevision(Base):
    __tablename__='question_revisions'
    __table_args__=(UniqueConstraint('question_id','version'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    question_id: Mapped[int]=mapped_column(ForeignKey('lab_questions.id'),index=True)
    version: Mapped[int]=mapped_column()
    content: Mapped[dict[str,Any]]=mapped_column(JSON)
    author_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    note: Mapped[str]=mapped_column(String(500),default='')
    created_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now())


class GradeDraft(Base):
    __tablename__='grade_drafts'
    __table_args__=(UniqueConstraint('attempt_id','reviewer_id'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    attempt_id: Mapped[int]=mapped_column(ForeignKey('lab_attempts.id'),index=True)
    reviewer_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    content: Mapped[dict[str,Any]]=mapped_column(JSON)
    updated_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),onupdate=func.now())


class GradeAudit(Base):
    __tablename__='grade_audits'
    id: Mapped[int]=mapped_column(primary_key=True)
    attempt_id: Mapped[int]=mapped_column(ForeignKey('lab_attempts.id'),index=True)
    reviewer_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    before: Mapped[dict[str,Any]]=mapped_column(JSON)
    after: Mapped[dict[str,Any]]=mapped_column(JSON)
    reason: Mapped[str]=mapped_column(String(1000),default='')
    created_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now())


class FeedbackSnippet(Base):
    __tablename__='feedback_snippets'
    id: Mapped[int]=mapped_column(primary_key=True)
    owner_id: Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    text: Mapped[str]=mapped_column(String(2000))
    created_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
