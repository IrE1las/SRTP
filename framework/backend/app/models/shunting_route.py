"""Reviewed shunting source data for the original photographed station."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShuntingDataset(Base):
    __tablename__ = 'shunting_datasets'

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    station_key: Mapped[str] = mapped_column(String(80), nullable=False)
    station_name: Mapped[str] = mapped_column(String(100), nullable=False)
    station_topology: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShuntingRoute(Base):
    __tablename__ = 'shunting_routes'
    __table_args__ = (UniqueConstraint('dataset_id', 'route_number', name='uq_shunting_source_number'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('shunting_datasets.id'), index=True, nullable=False)
    route_number: Mapped[int] = mapped_column(nullable=False)
    route_type: Mapped[str] = mapped_column(String(20), default='shunting', nullable=False)
    origin_label: Mapped[str] = mapped_column(String(30), nullable=False)
    route_name: Mapped[str] = mapped_column(String(120), nullable=False)
    fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rich_text: Mapped[dict[str, list[dict[str, str]]]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
