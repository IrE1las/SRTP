"""Original-application console with a separately preserved teaching profile."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.api.deps import require_roles
from app.models.user import User
from app.services.simulation_console.runtime import SimulationError, simulation_service
from app.services.simulation_console.station import public_station_package
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.reference_runtime import ReferenceSimulationService
from app.services.simulation_console.console_commands import operate


router = APIRouter()
AnyRole = Depends(require_roles("student", "teacher", "admin"))
reference_service = ReferenceSimulationService(reference_station_package())


def service_for(session_id):
    # The chosen service still validates ownership in _get; no cross-user access.
    return reference_service if session_id in reference_service.sessions else simulation_service


class SessionRequest(BaseModel):
    source: Literal['workbook', 'reference'] = 'workbook'
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


class ConsoleCommandRequest(BaseModel):
    type: Literal['SWITCH_TOTAL_NORMAL', 'SWITCH_TOTAL_REVERSE', 'SWITCH_SINGLE_LOCK',
                  'SWITCH_SINGLE_UNLOCK', 'SWITCH_SEAL', 'SWITCH_UNSEAL',
                  'SET_SWITCH_INDICATION', 'RESTORE_SWITCH_INDICATION',
                  'SET_SECTION_OCCUPANCY', 'CLEAR_SECTION_OCCUPANCY',
                  'CANCEL_ROUTE', 'REPEAT_OPEN_SIGNAL', 'MANUAL_UNLOCK_ROUTE',
                  'SIGNAL_SEAL', 'SIGNAL_UNSEAL', 'SIGNAL_LIGHT_ON', 'SIGNAL_LIGHT_OFF',
                  'SECTION_FAULT_UNLOCK', 'GUIDE_ARM', 'GUIDE_MAINTAIN', 'GUIDE_TOTAL_LOCK', 'GUIDE_TOTAL_UNLOCK',
                  'BLOCK_REQUEST', 'BLOCK_PEER_ACCEPT', 'BLOCK_RESET', 'BLOCK_ACCIDENT_RESET',
                  'BLOCK_DEPARTURE_AUX', 'BLOCK_RECEPTION_AUX', 'BLOCK_TOTAL_AUX']
    target: str = Field(min_length=1, max_length=80)
    payload: dict = Field(default_factory=dict)
    pin: str | None = Field(default=None, max_length=32)
    version: int | None = None


def _call(action, *args):
    try:
        return action(*args)
    except SimulationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/station")
def get_station(source: Literal['workbook', 'reference'] = 'workbook', current_user: User = AnyRole) -> dict:
    package = reference_station_package() if source == 'reference' else public_station_package()
    if current_user.role == "student":
        return {k: v for k, v in package.items() if k not in {"routes", "source"}}
    return package


@router.post("/sessions")
def create_session(request: SessionRequest, current_user: User = AnyRole) -> dict:
    if request.occupied_sections and current_user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="只有教师或管理员可预置占用场景")
    service = reference_service if request.source == 'reference' else simulation_service
    return _call(service.new_session, current_user.id,
                 request.interval_available, request.occupied_sections)


@router.get("/sessions/{session_id}")
def get_snapshot(session_id: str, current_user: User = AnyRole) -> dict:
    return _call(service_for(session_id).snapshot, session_id, current_user.id)


@router.get("/sessions/{session_id}/replay")
def get_replay(session_id: str, current_user: User = AnyRole) -> list[dict]:
    return _call(service_for(session_id).replay_frames, session_id, current_user.id)


@router.post("/sessions/{session_id}/buttons")
def select_button(session_id: str, request: ButtonRequest, current_user: User = AnyRole) -> dict:
    return _call(service_for(session_id).select_button, session_id, current_user.id, request.button, request.version)


@router.post("/sessions/{session_id}/clear-selection")
def clear_selection(session_id: str, request: VersionRequest, current_user: User = AnyRole) -> dict:
    return _call(service_for(session_id).clear_selection, session_id, current_user.id, request.version)


@router.post("/sessions/{session_id}/advance")
def advance_train(session_id: str, request: StepRequest,
                  current_user: User = Depends(require_roles("teacher", "admin"))) -> dict:
    return _call(service_for(session_id).step_train, session_id, current_user.id,
                 request.route_instance_id, request.version)


@router.post('/sessions/{session_id}/commands')
def console_command(session_id: str, request: ConsoleCommandRequest, current_user: User = AnyRole) -> dict:
    if request.type in {'SET_SWITCH_INDICATION', 'RESTORE_SWITCH_INDICATION',
                        'SET_SECTION_OCCUPANCY', 'CLEAR_SECTION_OCCUPANCY', 'BLOCK_PEER_ACCEPT'} and current_user.role == 'student':
        raise HTTPException(status_code=403, detail='只有教师或管理员可模拟设备故障、占用和邻站输入')
    service = service_for(session_id)
    return _call(operate, service, session_id, current_user.id, request.model_dump(exclude={'version'}), request.version)
