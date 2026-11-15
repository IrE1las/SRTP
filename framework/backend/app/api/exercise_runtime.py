"""Session-scoped exercise runtime API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.exercise import (
    ExerciseRuntimeResponse,
    ExerciseRuntimeRouteRequest,
    ExerciseRuntimeSectionRequest,
    ExerciseRuntimeSignalRequest,
    ExerciseRuntimeSwitchRequest,
    ExerciseRuntimeUnlockRequest,
)
from app.services.exercise.runtime_service import ExerciseRuntimeError, run_interlocking_operation

router = APIRouter()


@router.post("/routes/arrange", response_model=ExerciseRuntimeResponse)
def arrange_route_in_session(
    payload: ExerciseRuntimeRouteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseRuntimeResponse:
    """Arrange a route inside an exercise session and record the operation."""

    try:
        return run_interlocking_operation(
            db,
            current_user,
            payload.session_id,
            operation_type="select_route",
            target_code=f"{payload.entry_signal}->{payload.exit_signal}",
            target_type="route",
            request_payload=payload.model_dump(),
            operation=lambda engine: engine.arrange_route(payload.entry_signal, payload.exit_signal),
        )
    except ExerciseRuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/switches/operate", response_model=ExerciseRuntimeResponse)
def operate_switch_in_session(
    payload: ExerciseRuntimeSwitchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseRuntimeResponse:
    """Operate a switch inside an exercise session and record the operation."""

    try:
        return run_interlocking_operation(
            db,
            current_user,
            payload.session_id,
            operation_type="operate_switch",
            target_code=payload.switch_code,
            target_type="switch",
            request_payload=payload.model_dump(),
            operation=lambda engine: engine.operate_switch(payload.switch_code, payload.target_position),
        )
    except ExerciseRuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/sections/occupancy", response_model=ExerciseRuntimeResponse)
def update_section_occupancy_in_session(
    payload: ExerciseRuntimeSectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseRuntimeResponse:
    """Update section occupancy inside a session and record the operation."""

    try:
        return run_interlocking_operation(
            db,
            current_user,
            payload.session_id,
            operation_type="toggle_section",
            target_code=payload.section_code,
            target_type="section",
            request_payload=payload.model_dump(),
            operation=lambda engine: engine.update_section_occupancy(payload.section_code, payload.occupied),
        )
    except ExerciseRuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/routes/cancel", response_model=ExerciseRuntimeResponse)
def cancel_route_in_session(
    payload: ExerciseRuntimeSignalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseRuntimeResponse:
    """Cancel a route inside a session and record the operation."""

    try:
        return run_interlocking_operation(
            db,
            current_user,
            payload.session_id,
            operation_type="cancel_route",
            target_code=payload.signal_code,
            target_type="route",
            request_payload=payload.model_dump(),
            operation=lambda engine: engine.cancel_route(payload.signal_code),
        )
    except ExerciseRuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/unlock/manual", response_model=ExerciseRuntimeResponse)
def manual_unlock_in_session(
    payload: ExerciseRuntimeUnlockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseRuntimeResponse:
    """Manually unlock a section inside a session and record the operation."""

    try:
        return run_interlocking_operation(
            db,
            current_user,
            payload.session_id,
            operation_type="manual_unlock",
            target_code=payload.section_code,
            target_type="section",
            request_payload=payload.model_dump(),
            operation=lambda engine: engine.manual_unlock(payload.section_code),
        )
    except ExerciseRuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
