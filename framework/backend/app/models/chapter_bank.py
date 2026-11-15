"""Collected chapter questions, separate from scored laboratory exercises."""
from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ChapterBankQuestion(Base):
    __tablename__ = 'chapter_bank_questions'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    chapter: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    answer_status: Mapped[str] = mapped_column(String(40), index=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
