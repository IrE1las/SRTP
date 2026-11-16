"""Administrator-managed teaching sources, independent of question answers."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default='')
    filename: Mapped[str] = mapped_column(String(200))
    format: Mapped[str] = mapped_column(String(12))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pages: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class KnowledgeMigration(Base):
    __tablename__ = 'knowledge_migrations'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
