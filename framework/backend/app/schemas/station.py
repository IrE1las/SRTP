"""Station static data schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class StationResponse(BaseModel):
    """Station static configuration response."""

    id: int
    station_name: str
    station_code: str
    description: str | None
    station_config: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SignalResponse(BaseModel):
    """Signal static definition response."""

    id: int
    station_id: int
    signal_code: str
    signal_type: str
    position_x: int
    position_y: int
    direction: str

    model_config = ConfigDict(from_attributes=True)


class SwitchResponse(BaseModel):
    """Switch static definition response."""

    id: int
    station_id: int
    switch_code: str
    switch_type: str
    normal_position: str
    position_x: int
    position_y: int

    model_config = ConfigDict(from_attributes=True)


class SectionResponse(BaseModel):
    """Track section static definition response."""

    id: int
    station_id: int
    section_code: str
    section_type: str

    model_config = ConfigDict(from_attributes=True)


class InterlockingRouteResponse(BaseModel):
    """Interlocking route table response."""

    id: int
    station_id: int
    route_name: str
    entry_signal: str
    exit_signal: str
    route_type: str
    switches_required: dict[str, str]
    sections_required: list[str]
    hostile_routes: list[str]

    model_config = ConfigDict(from_attributes=True)


class StationDetailResponse(BaseModel):
    """Full station static data response."""

    station: StationResponse
    signals: list[SignalResponse]
    switches: list[SwitchResponse]
    sections: list[SectionResponse]
    routes: list[InterlockingRouteResponse]
