"""Isolated data.xls station simulation console API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.models.user import User
from app.services.simulation_console.runtime import SimulationError, simulation_service
from app.services.simulation_console.station import public_station_package


router = APIRouter()
AnyRole = Depends(require_roles("student", "teacher", "admin"))


class SessionRequest(BaseModel):
    interval_available: bool = True
    occupied_sections: list[str] = Field(default_factory=list)


class ButtonRequest(BaseModel):
    button: str
    version: int | None = None


class VersionRequest(BaseModel):
    version: int | None = None


class StepRequest(BaseModel):
    route_instance_id: str
    version: int | None = None


def _call(action, *args):
    try:
        return action(*args)
    except SimulationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/station")
def get_station(current_user: User = AnyRole) -> dict:
    package = public_station_package()
    if current_user.role == "student":
        return {k: v for k, v in package.items() if k not in {"routes", "source"}}
    return package


@router.post("/sessions")
def create_session(request: SessionRequest, current_user: User = AnyRole) -> dict:
    if request.occupied_sections and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="只有教师或管理员可预置占用场景")
    return _call(simulation_service.new_session, current_user.id,
                 request.interval_available, request.occupied_sections)


@router.get("/sessions/{session_id}")
def get_snapshot(session_id: str, current_user: User = AnyRole) -> dict:
    return _call(simulation_service.snapshot, session_id, current_user.id)


@router.get("/sessions/{session_id}/replay")
def get_replay(session_id: str, current_user: User = AnyRole) -> list[dict]:
    return _call(simulation_service.replay_frames, session_id, current_user.id)


@router.post("/sessions/{session_id}/buttons")
def select_button(session_id: str, request: ButtonRequest, current_user: User = AnyRole) -> dict:
    return _call(simulation_service.select_button, session_id, current_user.id, request.button, request.version)


@router.post("/sessions/{session_id}/clear-selection")
def clear_selection(session_id: str, request: VersionRequest, current_user: User = AnyRole) -> dict:
    return _call(simulation_service.clear_selection, session_id, current_user.id, request.version)


@router.post("/sessions/{session_id}/advance")
def advance_train(session_id: str, request: StepRequest,
                  current_user: User = Depends(require_roles("teacher", "admin"))) -> dict:
    return _call(simulation_service.step_train, session_id, current_user.id,
                 request.route_instance_id, request.version)
