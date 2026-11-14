"""Switch ORM model."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Switch(Base):
    """Static railway switch definition for a station."""

    __tablename__ = "switches"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True, nullable=False)
    switch_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    switch_type: Mapped[str] = mapped_column(String(20), nullable=False)
    normal_position: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    position_x: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position_y: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
