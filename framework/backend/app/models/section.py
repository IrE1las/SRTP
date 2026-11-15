"""Track section ORM model."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Section(Base):
    """Static track section definition for a station."""

    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True, nullable=False)
    section_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    section_type: Mapped[str] = mapped_column(String(20), nullable=False)
