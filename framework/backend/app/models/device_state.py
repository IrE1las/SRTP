"""Runtime device state ORM model."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceState(Base):
    """Current state for a signal, switch or track section."""

    __tablename__ = "device_states"
    __table_args__ = (
        UniqueConstraint("station_id", "device_type", "device_code", name="uq_device_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True, nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    device_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    state_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
