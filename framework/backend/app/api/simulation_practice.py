"""Student free practice on the topics 1–4 station, separate from assessed work."""
from fastapi import APIRouter, Depends
from app.api.deps import require_roles
from app.api.theory_console import (
    TheoryConsoleStore, SessionRequest, VersionRequest, ButtonRequest,
    StepRequest, CommandRequest, invoke,
)
from app.models.user import User
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.console_commands import operate

router = APIRouter()
student = require_roles('student')
store = TheoryConsoleStore(session_label='自由练习操作台')
SCOPE = 'free-practice'


@router.get('/station')
def station(user: User = Depends(student)):
    return {k: v for k, v in reference_station_package().items() if k not in {'routes', 'source'}}


@router.post('/sessions')
def create(body: SessionRequest, user: User = Depends(student)):
    return invoke(store.create, SCOPE, user.id, body.interval_available, body.occupied_sections)


@router.get('/sessions/{sid}')
def snapshot(sid: str, user: User = Depends(student)):
    return invoke(store.call, SCOPE, user.id, sid, store.engine.snapshot)


@router.get('/sessions/{sid}/replay')
def replay(sid: str, user: User = Depends(student)):
    return invoke(store.call, SCOPE, user.id, sid, store.engine.replay_frames)


@router.post('/sessions/{sid}/buttons')
def button(sid: str, body: ButtonRequest, user: User = Depends(student)):
    return invoke(store.call, SCOPE, user.id, sid, store.engine.select_button, body.button, body.version)


@router.post('/sessions/{sid}/clear-selection')
def clear(sid: str, body: VersionRequest, user: User = Depends(student)):
    return invoke(store.call, SCOPE, user.id, sid, store.engine.clear_selection, body.version)


@router.post('/sessions/{sid}/advance')
def advance(sid: str, body: StepRequest, user: User = Depends(student)):
    return invoke(store.call, SCOPE, user.id, sid, store.engine.step_train, body.route_instance_id, body.version)


@router.post('/sessions/{sid}/commands')
def command(sid: str, body: CommandRequest, user: User = Depends(student)):
    def action(session_id, owner_id):
        return operate(store.engine, session_id, owner_id, body.model_dump(exclude={'version'}), body.version)
    return invoke(store.call, SCOPE, user.id, sid, action)
