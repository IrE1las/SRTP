"""Atomic compare-and-swap state plus append-only event persistence."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models.module_one import ModuleOneAttempt, ModuleOneEvent
from app.services.simulation_console.runtime import SimulationService
from app.services.simulation_console.commands import dump_session, load_session, execute
from .experiment1_questions import QUESTIONS, public_question, validate_source
from .grader import grade


def live_feedback(question, events):
    result = grade(question, events)
    return {"completed": sum(c["passed"] for c in result["checkpoints"]),
            "message": "已完成步骤已记录；请继续按题干操作。"}


def find_attempt(db, aid, user, *, write=False):
    attempt = db.get(ModuleOneAttempt, aid)
    if attempt is None:
        raise HTTPException(404, "作答记录不存在")
    if attempt.owner_id != user.id and (write or user.role not in {"teacher", "admin"}):
        raise HTTPException(403, "无权访问或修改其他学生的作答")
    return attempt


def event_views(db, aid):
    return [{"command": e.command, "before_snapshot": e.before_snapshot, "response": e.response}
            for e in db.query(ModuleOneEvent).filter_by(attempt_id=aid).order_by(ModuleOneEvent.after_version)]


def snapshot_of(attempt):
    service = SimulationService()
    snapshot = service._snapshot(load_session(attempt.state))
    snapshot["version"] = attempt.version
    return snapshot


def attempt_view(attempt, db=None):
    view = {"attempt_id": attempt.id, "owner_id": attempt.owner_id, "question_id": attempt.question_id,
            "question": public_question(attempt.question_snapshot), "version": attempt.version,
            "status": attempt.status, "mode": attempt.mode, "preview": attempt.preview,
            "snapshot": snapshot_of(attempt), "notes": attempt.notes, "result": attempt.result,
            "started_at": attempt.started_at, "submitted_at": attempt.submitted_at}
    if db is not None and attempt.mode == "practice" and attempt.status == "in_progress":
        view["feedback"] = live_feedback(attempt.question_snapshot, event_views(db, attempt.id))
    return view


def create_attempt(db, user, question_id, scenario_id, mode):
    q = QUESTIONS.get(question_id)
    if q is None:
        raise HTTPException(404, "题目不存在")
    if q["status"] != "active":
        raise HTTPException(409, "本题待教师确认，不可启动或计分")
    if scenario_id != q["scenario_id"]:
        raise HTTPException(422, "场景与题目不匹配")
    try:
        source_fingerprint = validate_source()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    service = SimulationService()
    initial = service.new_session(user.id)
    session = service.sessions[initial["session_id"]]
    for sid, position in q["scenario"]["switch_positions"].items():
        session.switches[sid]["position"] = position
    initial = service._snapshot(session)
    initial["version"] = 0
    attempt = ModuleOneAttempt(id=str(uuid4()), owner_id=user.id, question_id=q["id"],
                               mode=mode, preview=user.role != "student", version=0,
                               question_snapshot=deepcopy(q), source_fingerprint=source_fingerprint,
                               state=dump_session(session), initial_snapshot=initial)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt_view(attempt, db)


def environment_allowed(question, session, command):
    kind, target = command["type"], command.get("target", "")
    if kind not in {"SET_SECTION_OCCUPANCY", "CLEAR_SECTION_OCCUPANCY", "SET_SWITCH_INDICATION", "RESTORE_SWITCH_INDICATION"}:
        return True
    value = {"CLEAR_SECTION_OCCUPANCY": "clear", "SET_SWITCH_INDICATION": "indication", "RESTORE_SWITCH_INDICATION": "restore_indication"}.get(kind, command.get("payload", {}).get("kind"))
    for rule in question["allowed_environment_commands"]:
        if rule["target"] != target or value not in rule["kinds"]:
            continue
        active = [r for r in session.routes.values() if r["status"] not in {"cancelled", "released"}]
        if rule["after_route"]:
            return any(r["route_id"] == rule["after_route"] and r["status"] in {"signal_open", "closed_locked"} and not r.get("train_started") for r in active)
        return not active
    return False


def apply_command(db, attempt, body):
    duplicate = db.query(ModuleOneEvent).filter_by(attempt_id=attempt.id, command_id=body["command_id"]).first()
    if duplicate:
        return duplicate.response
    if attempt.status != "in_progress":
        raise HTTPException(409, "已提交记录为只读")
    if body["expected_version"] != attempt.version:
        raise HTTPException(409, "状态版本已变化，请刷新后重试")
    # A source change cannot silently reinterpret a persisted attempt.
    try:
        if validate_source() != attempt.source_fingerprint:
            raise ValueError("源数据已变化，原作答只允许查看；请教师复核版本")
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    service = SimulationService()
    session = load_session(attempt.state)
    before = service._snapshot(session)
    before["version"] = attempt.version
    command = {k: deepcopy(body[k]) for k in ("type", "target", "payload")}
    if not environment_allowed(attempt.question_snapshot, session, command):
        result = service._reject(session, "本题不允许在此阶段对该设备设置此环境条件", reason_code="ENVIRONMENT_NOT_ALLOWED", devices=[command["target"]])
        result.update(state_delta={}, engine_events=[session.events[-1]])
    else:
        result = execute(service, session, command)
    new_version = attempt.version + 1
    result.update(event_id=str(uuid4()), before_version=attempt.version, after_version=new_version,
                  occurred_at=datetime.now(timezone.utc).isoformat())
    result["snapshot"]["version"] = new_version
    events = event_views(db, attempt.id) + [{"command": command, "before_snapshot": before, "response": result}]
    if attempt.mode == "practice":
        result["feedback"] = live_feedback(attempt.question_snapshot, events)
    changed = db.execute(update(ModuleOneAttempt).where(ModuleOneAttempt.id == attempt.id,
                           ModuleOneAttempt.version == body["expected_version"], ModuleOneAttempt.status == "in_progress")
                         .values(state=dump_session(session), version=new_version).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        duplicate = db.query(ModuleOneEvent).filter_by(attempt_id=attempt.id, command_id=body["command_id"]).first()
        if duplicate:
            return duplicate.response
        raise HTTPException(409, "并发操作导致版本冲突，请刷新")
    db.add(ModuleOneEvent(id=result["event_id"], attempt_id=attempt.id, command_id=body["command_id"],
                         after_version=new_version, command=command, before_snapshot=before, response=result))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        duplicate = db.query(ModuleOneEvent).filter_by(attempt_id=attempt.id, command_id=body["command_id"]).first()
        if duplicate:
            return duplicate.response
        raise HTTPException(409, "并发操作冲突") from None
    db.expire_all()
    return result


def submit_attempt(db, attempt, expected_version, notes):
    if attempt.status == "submitted":
        return attempt_view(attempt)
    if expected_version != attempt.version:
        raise HTTPException(409, "状态版本已变化，请刷新后提交")
    result = grade(attempt.question_snapshot, event_views(db, attempt.id))
    changed = db.execute(update(ModuleOneAttempt).where(ModuleOneAttempt.id == attempt.id,
                         ModuleOneAttempt.version == expected_version, ModuleOneAttempt.status == "in_progress")
                         .values(status="submitted", version=expected_version + 1, notes=notes, result=result,
                                 submitted_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        db.refresh(attempt)
        if attempt.status == "submitted":
            return attempt_view(attempt)
        raise HTTPException(409, "并发提交冲突，请刷新")
    db.commit()
    db.refresh(attempt)
    return attempt_view(attempt)
