"""Runtime route state ORM model."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RouteState(Base):
    """Current state for an arranged interlocking route."""

    __tablename__ = "route_states"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True, nullable=False)
    route_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entry_signal: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    exit_signal: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    locked_switches: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    locked_sections: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    opened_signal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
