"""Three-module catalog and authenticated durable experiment-one API."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User
from app.models.module_one import ModuleOneAttempt
from app.services.module_one.experiment1_questions import QUESTIONS, public_question
from app.services.module_one import repository as repo
from app.services.simulation_console.station import public_station_package

router = APIRouter()
reader = Depends(require_roles("student", "teacher", "admin"))
teacher = Depends(require_roles("teacher", "admin"))


class AttemptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    scenario_id: str
    mode: Literal["practice", "exam"] = "practice"


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: UUID
    expected_version: int = Field(ge=0)
    type: str = Field(min_length=1, max_length=60)
    target: str = Field(default="", max_length=80)
    payload: dict = Field(default_factory=dict, max_length=4)


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    notes: str = Field(default="", max_length=6000)


@router.get("/modules")
def modules(user: User = reader):
    return [
        {"id": "one", "title": "模块一 · 一号车站", "station_id": "station_1", "status": "active", "description": "动态进路与道岔操作，观察联锁结果并复盘操作过程。", "experiments": [{"id": n, "status": "active" if n == 1 else "planned"} for n in range(1, 5)]},
        {"id": "two", "title": "模块二 · 二号车站", "station_id": "original-photo-station", "status": "resources", "description": "联锁表绘制与逐栏错误定位，复用原站场作答资源。", "experiments": [{"id": n, "status": "resources"} for n in (5, 6)]},
        {"id": "three", "title": "模块三 · 区间控制", "station_id": None, "status": "planned", "description": "半自动闭塞与 ZPW-2000 区间信号，业务规则规划中。", "experiments": [{"id": n, "status": "planned"} for n in (7, 8)]},
    ]


@router.get("/module-one/station")
def station(user: User = reader):
    package = public_station_package()
    return {k: v for k, v in package.items() if k not in {"routes", "source"}}


@router.get("/module-one/experiment-1/questions")
def questions(db: Session = Depends(get_db), user: User = reader):
    attempts = db.query(ModuleOneAttempt).filter_by(owner_id=user.id).order_by(ModuleOneAttempt.started_at.desc()).all()
    latest = {}
    for a in attempts:
        latest.setdefault(a.question_id, {"attempt_id": a.id, "status": a.status, "mode": a.mode})
    return [{**public_question(q), "progress": latest.get(q["id"])} for q in QUESTIONS.values()]


@router.get("/module-one/experiment-1/questions/{qid}/configuration")
def configuration(qid: str, user: User = teacher):
    if qid not in QUESTIONS:
        raise HTTPException(404, "题目不存在")
    return QUESTIONS[qid]


@router.post("/module-one/experiment-1/attempts", status_code=201)
def create(body: AttemptRequest, db: Session = Depends(get_db), user: User = reader):
    return repo.create_attempt(db, user, body.question_id, body.scenario_id, body.mode)


@router.get("/module-one/attempts")
def attempts(db: Session = Depends(get_db), user: User = reader):
    query = db.query(ModuleOneAttempt, User).join(User, User.id == ModuleOneAttempt.owner_id)
    if user.role == "student":
        query = query.filter(ModuleOneAttempt.owner_id == user.id)
    return [{"attempt_id": a.id, "question_id": a.question_id, "title": a.question_snapshot["title"],
             "owner_id": a.owner_id, "student_name": u.real_name or u.username, "status": a.status,
             "preview": a.preview, "mode": a.mode, "started_at": a.started_at,
             "score": a.result.get("score") if a.result else None}
            for a, u in query.order_by(ModuleOneAttempt.started_at.desc()).limit(300)]


@router.get("/module-one/attempts/{aid}")
def restore(aid: str, db: Session = Depends(get_db), user: User = reader):
    return repo.attempt_view(repo.find_attempt(db, aid, user), db)


@router.post("/module-one/attempts/{aid}/commands")
def command(aid: str, body: CommandRequest, db: Session = Depends(get_db), user: User = reader):
    return repo.apply_command(db, repo.find_attempt(db, aid, user, write=True), body.model_dump(mode="json"))


@router.post("/module-one/attempts/{aid}/submit")
def submit(aid: str, body: SubmitRequest, db: Session = Depends(get_db), user: User = reader):
    return repo.submit_attempt(db, repo.find_attempt(db, aid, user, write=True), body.expected_version, body.notes)


@router.get("/module-one/attempts/{aid}/result")
def result(aid: str, db: Session = Depends(get_db), user: User = reader):
    attempt = repo.find_attempt(db, aid, user)
    if attempt.status != "submitted":
        raise HTTPException(409, "提交后可查看完整分项结果")
    return attempt.result


@router.get("/module-one/attempts/{aid}/replay")
def replay(aid: str, db: Session = Depends(get_db), user: User = reader):
    attempt = repo.find_attempt(db, aid, user)
    events = repo.event_views(db, aid)
    if attempt.mode == "exam" and attempt.status != "submitted" and user.role == "student":
        # Current observations remain visible, grading rules do not.
        for event in events:
            event["response"].pop("feedback", None)
    return {"attempt_id": aid, "initial_snapshot": attempt.initial_snapshot, "events": events, "result": attempt.result}
