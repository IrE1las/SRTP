"""Question-bound standard-station observation for theory topics 1 through 4."""
from threading import RLock
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.orm import Session
from app.api.deps import require_roles
from app.api.lab_topics import find_question
from app.core.database import get_db
from app.models.user import User
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.reference_runtime import ReferenceSimulationService
from app.services.simulation_console.runtime import SimulationError
from app.services.simulation_console.console_commands import operate

router=APIRouter()
reader=require_roles('student','teacher','admin')

class TheoryConsoleStore:
    """At most one active isolated console per owner/question; no grading or shared station."""
    def __init__(self):
        self.engine=ReferenceSimulationService(reference_station_package())
        self.bindings={}
        self.lock=RLock()

    def create(self,key,user_id,interval_available,occupied):
        with self.lock:
            snapshot=self.engine.new_session(user_id,interval_available,occupied)
            for sid,binding in list(self.bindings.items()):
                if binding==(key,user_id):
                    self.bindings.pop(sid)
                    with self.engine.sessions_mutex:
                        self.engine.sessions.pop(sid,None)
                    self.engine.reference_states.pop(sid,None)
            self.bindings[snapshot['session_id']]=(key,user_id)
            return snapshot

    def call(self,key,user_id,sid,action,*args):
        with self.lock:
            if self.bindings.get(sid)!=(key,user_id):
                raise SimulationError('本题操作台会话不存在、已重新初始化或无权访问')
            return action(sid,user_id,*args)

store=TheoryConsoleStore()

class Body(BaseModel):
    model_config=ConfigDict(extra='forbid')

class SessionRequest(Body):
    interval_available:bool=True
    occupied_sections:list[str]=Field(default_factory=list,max_length=35)

class VersionRequest(Body):
    version:StrictInt=Field(ge=0)

class ButtonRequest(VersionRequest):
    button:str=Field(min_length=1,max_length=80)

class StepRequest(VersionRequest):
    route_instance_id:str=Field(min_length=1,max_length=80)

class CommandRequest(VersionRequest):
    type:Literal['SWITCH_TOTAL_NORMAL','SWITCH_TOTAL_REVERSE','SWITCH_SINGLE_LOCK','SWITCH_SINGLE_UNLOCK',
                 'SWITCH_SEAL','SWITCH_UNSEAL','SET_SWITCH_INDICATION','RESTORE_SWITCH_INDICATION',
                 'SET_SECTION_OCCUPANCY','CLEAR_SECTION_OCCUPANCY','CANCEL_ROUTE','REPEAT_OPEN_SIGNAL',
                 'MANUAL_UNLOCK_ROUTE','SIGNAL_SEAL','SIGNAL_UNSEAL','SIGNAL_LIGHT_ON','SIGNAL_LIGHT_OFF',
                 'SECTION_FAULT_UNLOCK','GUIDE_ARM','GUIDE_MAINTAIN','GUIDE_TOTAL_LOCK','GUIDE_TOTAL_UNLOCK',
                 'BLOCK_REQUEST','BLOCK_PEER_ACCEPT','BLOCK_RESET','BLOCK_ACCIDENT_RESET',
                 'BLOCK_DEPARTURE_AUX','BLOCK_RECEPTION_AUX','BLOCK_TOTAL_AUX']
    target:str=Field(min_length=1,max_length=80)
    payload:dict=Field(default_factory=dict,max_length=10)
    pin:str|None=Field(default=None,max_length=32,repr=False)

def question_access(key:str,db:Session=Depends(get_db),user:User=Depends(reader)):
    q=find_question(db,key)
    if q.topic not in range(1,5):
        raise HTTPException(404,'该专题使用联锁表平台，不使用联锁仿真操作台')
    return key,user

def invoke(operation,*args):
    try:
        return operation(*args)
    except SimulationError as exc:
        raise HTTPException(409,str(exc)) from exc

@router.get('/questions/{key}/console/station')
def station(access=Depends(question_access)):
    _,user=access
    package=reference_station_package()
    return {k:v for k,v in package.items() if user.role!='student' or k not in {'routes','source'}}

@router.post('/questions/{key}/console/sessions')
def create(body:SessionRequest,access=Depends(question_access)):
    key,user=access
    # Theory observation is an isolated sandbox. Presets, faults and train moves
    # affect this question's console only; they do not modify or score an answer.
    return invoke(store.create,key,user.id,body.interval_available,body.occupied_sections)

@router.get('/questions/{key}/console/sessions/{sid}')
def snapshot(sid:str,access=Depends(question_access)):
    key,user=access
    return invoke(store.call,key,user.id,sid,store.engine.snapshot)

@router.get('/questions/{key}/console/sessions/{sid}/replay')
def replay(sid:str,access=Depends(question_access)):
    key,user=access
    return invoke(store.call,key,user.id,sid,store.engine.replay_frames)

@router.post('/questions/{key}/console/sessions/{sid}/buttons')
def button(sid:str,body:ButtonRequest,access=Depends(question_access)):
    key,user=access
    return invoke(store.call,key,user.id,sid,store.engine.select_button,body.button,body.version)

@router.post('/questions/{key}/console/sessions/{sid}/clear-selection')
def clear(sid:str,body:VersionRequest,access=Depends(question_access)):
    key,user=access
    return invoke(store.call,key,user.id,sid,store.engine.clear_selection,body.version)

@router.post('/questions/{key}/console/sessions/{sid}/advance')
def advance(sid:str,body:StepRequest,access=Depends(question_access)):
    key,user=access
    return invoke(store.call,key,user.id,sid,store.engine.step_train,body.route_instance_id,body.version)

@router.post('/questions/{key}/console/sessions/{sid}/commands')
def command(sid:str,body:CommandRequest,access=Depends(question_access)):
    key,user=access
    def action(session_id,owner_id):
        return operate(store.engine,session_id,owner_id,body.model_dump(exclude={'version'}),body.version)
    return invoke(store.call,key,user.id,sid,action)
