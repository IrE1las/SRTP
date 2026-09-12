"""Interlocking operation schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field

SwitchPosition = Literal["normal", "reverse"]


class RouteArrangeRequest(BaseModel):
    """Request to check or arrange a route."""

    station_id: int
    entry_signal: str = Field(min_length=1, max_length=20)
    exit_signal: str = Field(min_length=1, max_length=20)


class RouteCancelRequest(BaseModel):
    """Request to cancel a route by its entry signal."""

    station_id: int
    signal_code: str = Field(min_length=1, max_length=20)


class ManualUnlockRequest(BaseModel):
    """Request to manually unlock resources related to a section."""

    station_id: int
    section_code: str = Field(min_length=1, max_length=20)


class SwitchOperateRequest(BaseModel):
    """Request to manually operate a switch."""

    station_id: int
    switch_code: str = Field(min_length=1, max_length=20)
    target_position: SwitchPosition


class SectionOccupancyUpdateRequest(BaseModel):
    """Request to update track section occupancy."""

    station_id: int
    section_code: str = Field(min_length=1, max_length=20)
    occupied: bool


class DeviceSnapshot(BaseModel):
    """Runtime state for a single device."""

    code: str
    state: dict[str, Any]


class RouteSnapshot(BaseModel):
    """Runtime state for a single route."""

    route_name: str
    entry_signal: str
    exit_signal: str
    status: str
    locked_switches: dict[str, str]
    locked_sections: list[str]
    opened_signal: str | None = None


class StationSnapshotResponse(BaseModel):
    """Full station runtime state snapshot."""

    station_id: int
    signals: dict[str, dict[str, Any]]
    switches: dict[str, dict[str, Any]]
    sections: dict[str, dict[str, Any]]
    active_routes: list[RouteSnapshot]
    locked_routes: list[str]


class RouteConditionCheckResponse(BaseModel):
    """Route condition check result."""

    ok: bool
    message: str
    failed_rules: list[str] = Field(default_factory=list)
    route_name: str | None = None


class InterlockingActionResponse(BaseModel):
    """Response for an interlocking operation."""

    success: bool
    message: str
    snapshot: StationSnapshotResponse
