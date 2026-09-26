"""Independent report scenarios and persistence/security contract checks."""
from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.user import User
from app.models.module_one import ModuleOneAttempt, ModuleOneEvent
from app.services.module_one.experiment1_questions import QUESTIONS, validate_source
from app.services.module_one import repository as repo
from app.services.simulation_console.commands import execute, dump_session, load_session
from app.services.simulation_console.runtime import SimulationService


@pytest.fixture()
def users(db_session):
    result = []
    for name, role in [("one_student", "student"), ("other_student", "student"), ("one_teacher", "teacher")]:
        user = User(username=name, password_hash="unused-test-hash", real_name=name, role=role)
        db_session.add(user)
        result.append(user)
    db_session.commit()
    return result


def headers(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


def cmd(token, snap):
    parts = token.split(":")
    mapping = {"N": "SWITCH_TOTAL_NORMAL", "R": "SWITCH_TOTAL_REVERSE", "L": "SWITCH_SINGLE_LOCK",
               "U": "SWITCH_SINGLE_UNLOCK", "S": "SWITCH_SEAL", "I": "SET_SWITCH_INDICATION"}
    if parts[0] in mapping:
        return {"type": mapping[parts[0]], "target": parts[1], "payload": {}}
    if parts[0] in {"F", "V", "C"}:
        return {"type": "CLEAR_SECTION_OCCUPANCY" if parts[0] == "C" else "SET_SECTION_OCCUPANCY", "target": parts[1], "payload": {} if parts[0] == "C" else {"kind": "fault" if parts[0] == "F" else "vehicle"}}
    if parts[0] in {"O", "X"}:
        instance = next(r for r in reversed(snap["routes"]) if r["route_id"] == parts[1])
        return {"type": "REPEAT_OPEN_SIGNAL" if parts[0] == "O" else "CANCEL_ROUTE", "target": instance["id"], "payload": {}}
    return {"type": "PRESS_BUTTON", "target": token, "payload": {}}


SCENARIOS = {
    "E1-1-1": "R:5/7 N:5/7",
    "E1-1-2-0": "L:9/11 N:9/11 R:9/11 U:9/11 R:9/11 N:9/11",
    "E1-1-2-1": "L:9/11 N:9/11 R:9/11 U:9/11 R:9/11 N:9/11",
    "E1-1-3": "V:7DG R:5/7 N:5/7",
    "E1-1-4": "S:5/7 R:5/7 N:5/7 D3A D13A",
    "E1-2A": "D3A D13A R:5/7 SIIIDA D9A X:146",
    "E1-2B-1-0": "N:5/7 L:5/7 D3A D13A",
    "E1-2B-1-1": "R:5/7 L:5/7 D3A D13A",
    "E1-2B-2-0": "N:5/7 S:5/7 D3A D13A",
    "E1-2B-2-1": "R:5/7 S:5/7 D3A D13A",
    "E1-2B-3": "F:5DG D3A D13A",
    "E1-2B-4": "I:5/7 D3A D13A",
    "E1-2B-5": "V:9-15DG D3A D13A",
    "E1-2C": "D3A D13A F:5DG O:146 C:5DG O:146",
    "E1-3-1": "D1A S4DA",
    "E1-3-2": "V:1/19WG D1A S4DA",
    "E1-3-3": "D1A S4DA F:19-27DG O:116 C:19-27DG O:116",
    "E1-4-1": "S4DA D15A D5A D1A",
    "E1-4-2": "SIIILA BA XFLA",
    "E1-4-3": "XLA BA SIIILA",
    "E1-5-1": "V:IIIG XLA SIIILA",
    "E1-5-2": "F:3DG XLA SIIILA",
    "E1-5-3": "SLA XIIILA XLA SIIILA",
    "E1-5-4": "SLA XIIILA D12A XIIIDA",
}


def run(db, user, qid, script, mode="practice"):
    view = repo.create_attempt(db, user, qid, qid, mode)
    for token in script.split():
        attempt = db.get(ModuleOneAttempt, view["attempt_id"])
        response = repo.apply_command(db, attempt, {"command_id": str(uuid4()), "expected_version": view["version"], **cmd(token, view["snapshot"])})
        view.update(snapshot=response["snapshot"], version=response["after_version"])
    return db.get(ModuleOneAttempt, view["attempt_id"])


@pytest.mark.parametrize("qid,script", SCENARIOS.items())
def test_every_revised_report_scenario(db_session, users, qid, script):
    attempt = run(db_session, users[0], qid, script)
    result = repo.submit_attempt(db_session, attempt, attempt.version, "原因由教师审阅")
    assert result["result"]["score"] == 100, result["result"]
    assert result["result"]["notes_scored"] is False
    assert result["notes"] == "原因由教师审阅"


def test_source_and_coverage():
    assert len(validate_source()) == 64
    assert set(SCENARIOS) == {k for k, q in QUESTIONS.items() if q["status"] == "active"}


def test_equivalent_fault_occupancy_and_final_state(db_session, users):
    attempt = run(db_session, users[0], "E1-2B-5", "F:9-15DG D3A D13A")
    assert repo.submit_attempt(db_session, attempt, attempt.version, "")["result"]["score"] == 100
    altered = run(db_session, users[0], "E1-1-1", "R:5/7 N:5/7 R:5/7")
    assert repo.submit_attempt(db_session, altered, altered.version, "")["result"]["score"] < 100


def test_atomic_turnouts_fault_recovery_and_cancel_guard():
    service = SimulationService()
    initial = service.new_session(1)
    session = service.sessions[initial["session_id"]]
    def do(token):
        return execute(service, session, cmd(token, service._snapshot(session)))
    do("V:7DG")
    denied = do("R:5/7")
    assert denied["reason_code"] == "SECTION_OCCUPIED"
    assert denied["state_delta"]["switches"] == {}
    do("C:7DG")
    do("D3A"); do("D13A")
    locked = deepcopy(session.sections["5DG"]["owners"])
    do("F:5DG")
    assert session.signals["D3"]["aspect"] is None
    assert do("O:146")["reason_code"] == "SECTION_OCCUPIED"
    assert do("X:146")["reason_code"] == "SECTION_OCCUPIED"
    do("C:5DG")
    assert session.signals["D3"]["aspect"] is None
    assert session.sections["5DG"]["owners"] == locked
    assert do("O:146")["accepted"]
    route = next(iter(session.routes.values()))
    route["train_started"] = True
    assert do("X:146")["reason_code"] == "APPROACH_LOCKED"
    assert session.sections["5DG"]["owners"] == locked
    # A denied teacher train step must not mark an untouched route as started.
    other = service.new_session(2)
    service.select_button(other["session_id"], 2, "D3A")
    service.select_button(other["session_id"], 2, "D13A")
    other_session = service.sessions[other["session_id"]]
    other_route = next(iter(other_session.routes.values()))
    other_session.sections["5DG"]["occupied"] = True
    assert not service.step_train(other_session.id, 2, other_route["id"])["accepted"]
    assert not other_route["train_started"]


@pytest.mark.parametrize("script,expected", [("XLA SIIILA", 0), ("D1A S4DA V:1/19WG", 0), ("V:1/19WG UNKNOWN", 50)])
def test_wrong_route_order_or_arbitrary_refusal_is_not_correct(db_session, users, script, expected):
    attempt = run(db_session, users[0], "E1-3-2", script)
    assert repo.submit_attempt(db_session, attempt, attempt.version, "")["result"]["score"] == expected


def test_persistence_rebuilds_runtime_and_freezes_submission(db_session, users):
    attempt = run(db_session, users[0], "E1-2C", "D3A D13A F:5DG O:146")
    aid, owner, engine = attempt.id, users[0].id, db_session.get_bind()
    # New ORM session and fresh SimulationService: no live runtime singleton.
    with Session(engine) as restored_db:
        saved = restored_db.get(ModuleOneAttempt, aid)
        assert repo.snapshot_of(saved)["signals"]["D3"]["aspect"] is None
        for token in ["C:5DG", "O:146"]:
            response = repo.apply_command(restored_db, saved, {"command_id": str(uuid4()), "expected_version": saved.version, **cmd(token, repo.snapshot_of(saved))})
            saved = restored_db.get(ModuleOneAttempt, aid)
        view = repo.submit_attempt(restored_db, saved, saved.version, "saved")
        assert view["result"]["score"] == 100
    with Session(engine) as again:
        saved = again.get(ModuleOneAttempt, aid)
        assert saved.owner_id == owner and saved.result["score"] == 100
        assert len(repo.event_views(again, aid)) == 6


def test_api_permissions_idempotency_hidden_answers_and_versions(client, db_session, users):
    student, other, teacher = map(headers, users)
    for url in ["/api/module-one/station", "/api/simulation-console/station"]:
        assert "routes" not in client.get(url, headers=student).json()
    questions = client.get("/api/module-one/experiment-1/questions", headers=student).json()
    assert all("checkpoints" not in q and "fingerprint" not in q for q in questions)
    assert client.get("/api/module-one/experiment-1/questions/E1-1-1/configuration", headers=student).status_code == 403
    for n in (5, 6, 7):
        key = f"E1-5-{n}"
        assert client.post("/api/module-one/experiment-1/attempts", headers=student, json={"question_id": key, "scenario_id": key}).status_code == 409
    view = client.post("/api/module-one/experiment-1/attempts", headers=student, json={"question_id": "E1-1-1", "scenario_id": "E1-1-1", "mode": "exam"}).json()
    assert "feedback" not in view
    url = f"/api/module-one/attempts/{view['attempt_id']}"
    assert client.get(url, headers=other).status_code == 403
    assert client.get(url + "/replay", headers=teacher).status_code == 200
    payload = {"command_id": str(uuid4()), "expected_version": 0, "type": "SWITCH_TOTAL_REVERSE", "target": "5/7"}
    assert client.post(url + "/commands", headers=teacher, json=payload).status_code == 403
    first = client.post(url + "/commands", headers=student, json=payload).json()
    assert "feedback" not in first
    assert client.post(url + "/commands", headers=student, json=payload).json() == first
    assert db_session.query(ModuleOneEvent).count() == 1
    stale = {**payload, "command_id": str(uuid4())}
    assert client.post(url + "/commands", headers=student, json=stale).status_code == 409
    forbidden = {**stale, "expected_version": 1, "type": "SET_SECTION_OCCUPANCY", "target": "IIIG", "payload": {"kind": "vehicle"}}
    denied = client.post(url + "/commands", headers=student, json=forbidden).json()
    assert denied["reason_code"] == "ENVIRONMENT_NOT_ALLOWED" and denied["after_version"] == 2
    assert not denied["snapshot"]["sections"]["IIIG"]["occupied"]
    assert client.get(url + "/result", headers=student).status_code == 409
    submitted = client.post(url + "/submit", headers=student, json={"expected_version": 2, "notes": "not graded"}).json()
    again = client.post(url + "/submit", headers=student, json={"expected_version": 2}).json()
    assert again == submitted and again["result"]["score"] == 50
    assert client.post(url + "/commands", headers=student, json={**stale, "command_id": str(uuid4()), "expected_version": 3}).status_code == 409
    # A retry after submit still gets its original immutable command receipt.
    assert client.post(url + "/commands", headers=student, json=payload).json() == first


def test_fault_timing_guard_and_selection_timeout(db_session, users, monkeypatch):
    view = repo.create_attempt(db_session, users[0], "E1-2C", "E1-2C", "practice")
    a = db_session.get(ModuleOneAttempt, view["attempt_id"])
    denied = repo.apply_command(db_session, a, {"command_id": str(uuid4()), "expected_version": 0, **cmd("F:5DG", view["snapshot"])})
    assert denied["reason_code"] == "ENVIRONMENT_NOT_ALLOWED"
    service = SimulationService()
    state = service.new_session(1)
    session = service.sessions[state["session_id"]]
    execute(service, session, cmd("D3A", state))
    stored = dump_session(session)
    stored["selection_expires_at"] = 1  # Simulate process restart after deadline.
    restored = load_session(stored)
    result = execute(service, restored, cmd("D13A", state))
    assert any(e["kind"] == "selection_timeout" for e in result["engine_events"])
    assert result["route_id"] is None and not restored.routes


def test_two_database_writers_cannot_lose_events(db_session, users):
    from fastapi import HTTPException
    view = repo.create_attempt(db_session, users[0], "E1-1-1", "E1-1-1", "practice")
    aid = view["attempt_id"]
    with Session(db_session.get_bind()) as first, Session(db_session.get_bind()) as second:
        a, b = first.get(ModuleOneAttempt, aid), second.get(ModuleOneAttempt, aid)
        command = {"command_id": str(uuid4()), "expected_version": 0, **cmd("R:5/7", view["snapshot"])}
        receipt = repo.apply_command(first, a, command)
        # Same command is safe even from an ORM session holding an old version.
        assert repo.apply_command(second, b, command) == receipt
        with pytest.raises(HTTPException) as exc:
            repo.apply_command(second, b, {**command, "command_id": str(uuid4()), "type": "SWITCH_TOTAL_NORMAL"})
        assert exc.value.status_code == 409
    db_session.expire_all()
    assert db_session.query(ModuleOneEvent).filter_by(attempt_id=aid).count() == 1
    assert repo.snapshot_of(db_session.get(ModuleOneAttempt, aid))["switches"]["5"]["position"] == 1
