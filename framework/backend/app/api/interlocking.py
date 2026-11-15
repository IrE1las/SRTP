"""Interlocking API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User
from app.schemas.interlocking import (
    InterlockingActionResponse,
    ManualUnlockRequest,
    RouteArrangeRequest,
    RouteCancelRequest,
    RouteConditionCheckResponse,
    SectionOccupancyUpdateRequest,
    StationSnapshotResponse,
    SwitchOperateRequest,
)
from app.schemas.station import InterlockingRouteResponse, StationDetailResponse
from app.services.interlocking.engine import InterlockingEngine
from app.services.interlocking.seed_service import reset_station_runtime_state, seed_default_station
from app.services.interlocking.repository import InterlockingRepository

router = APIRouter()

AnyRole = Depends(require_roles("student", "teacher", "admin"))


@router.post("/stations/seed-default")
def seed_standard_station(
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> dict[str, int | str]:
    """Seed the default station and route table."""

    station = seed_default_station(db)
    return {"station_id": station.id, "station_name": station.station_name}


@router.post("/stations/{station_id}/reset-state")
def reset_station_state(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> dict[str, int | str]:
    """Reset runtime state for a station."""

    reset_station_runtime_state(db, station_id)
    return {"station_id": station_id, "message": "站场运行状态已重置"}


@router.get("/stations/{station_id}/detail", response_model=StationDetailResponse)
def get_station_detail(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> StationDetailResponse:
    """Return station static data for SVG rendering."""

    detail = InterlockingRepository(db, station_id).get_station_detail()
    if detail["station"] is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="站场不存在")
    return StationDetailResponse.model_validate(detail)


@router.get("/stations/{station_id}/snapshot", response_model=StationSnapshotResponse)
def get_station_snapshot(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> StationSnapshotResponse:
    """Return current station runtime state."""

    return InterlockingEngine(db, station_id).get_station_snapshot()


@router.get("/stations/{station_id}/routes", response_model=list[InterlockingRouteResponse])
def list_routes(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> list[InterlockingRouteResponse]:
    """Return interlocking route table entries for a station."""

    routes = InterlockingRepository(db, station_id).list_route_tables()
    return [InterlockingRouteResponse.model_validate(route) for route in routes]


@router.post("/routes/check", response_model=RouteConditionCheckResponse)
def check_route(
    request: RouteArrangeRequest,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> RouteConditionCheckResponse:
    """Check whether a route can be arranged."""

    return InterlockingEngine(db, request.station_id).check_route_conditions(
        request.entry_signal,
        request.exit_signal,
    )


@router.post("/routes/arrange", response_model=InterlockingActionResponse)
def arrange_route(
    request: RouteArrangeRequest,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> InterlockingActionResponse:
    """Arrange and lock a route."""

    response = InterlockingEngine(db, request.station_id).arrange_route(
        request.entry_signal,
        request.exit_signal,
    )
    if not response.success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=response.message)
    return response


@router.post("/routes/cancel", response_model=InterlockingActionResponse)
def cancel_route(
    request: RouteCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> InterlockingActionResponse:
    """Cancel a locked route."""

    response = InterlockingEngine(db, request.station_id).cancel_route(request.signal_code)
    if not response.success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=response.message)
    return response


@router.post("/switches/operate", response_model=InterlockingActionResponse)
def operate_switch(
    request: SwitchOperateRequest,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> InterlockingActionResponse:
    """Manually operate a switch."""

    response = InterlockingEngine(db, request.station_id).operate_switch(
        request.switch_code,
        request.target_position,
    )
    if not response.success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=response.message)
    return response


@router.post("/sections/occupancy", response_model=InterlockingActionResponse)
def update_section_occupancy(
    request: SectionOccupancyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> InterlockingActionResponse:
    """Update section occupancy and trigger related signal closure."""

    return InterlockingEngine(db, request.station_id).update_section_occupancy(
        request.section_code,
        request.occupied,
    )


@router.post("/unlock/manual", response_model=InterlockingActionResponse)
def manual_unlock(
    request: ManualUnlockRequest,
    db: Session = Depends(get_db),
    current_user: User = AnyRole,
) -> InterlockingActionResponse:
    """Manually unlock resources related to a section."""

    response = InterlockingEngine(db, request.station_id).manual_unlock(request.section_code)
    if not response.success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=response.message)
    return response
