"""Interlocking route table ORM model."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InterlockingTable(Base):
    """Static interlocking route definition driven by railway route tables."""

    __tablename__ = "interlocking_tables"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True, nullable=False)
    route_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entry_signal: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    exit_signal: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    route_type: Mapped[str] = mapped_column(String(20), nullable=False)
    switches_required: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    sections_required: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    hostile_routes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
