"""Station ORM model."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Station(Base):
    """Railway station static configuration."""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    station_name: Mapped[str] = mapped_column(String(100), nullable=False)
    station_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    station_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
