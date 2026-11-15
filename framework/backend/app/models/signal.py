"""Signal ORM model."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Signal(Base):
    """Static signal definition for a station."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True, nullable=False)
    signal_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    position_x: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position_y: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
