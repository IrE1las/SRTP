"""S5 HTTP/SQLite contracts with a controlled server clock; no browser or real AI."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.models import User
from app.models.exam import Exam, ExamParticipant, ExamAttempt, ExamControlEvent
from app.models.operation import OperationSession, OperationEvent, OperationVersion
from app.services import exams as service
from tests.helpers import auth_headers
from tests.test_s3_operations import BASE, draft, record_standard

ROOT = '/api/exams'


@pytest.fixture()
def clock(monkeypatch):
    value = [datetime(2030, 1, 2, 4, 0, 0)]
    monkeypatch.setattr(service, 'now', lambda: value[0])
    return value


@pytest.fixture()
def course(client, db_session, clock):
    roles = {role: auth_headers(client, 's5_' + role, role) for role in ['teacher', 'student', 'admin']}
    roles['peer'] = auth_headers(client, 's5_peer', 'student')
    q = draft(client, roles['teacher'])
    q, _ = record_standard(client, roles['teacher'], q['id'])
    response = client.post(f"{BASE}/questions/{q['id']}/publish", headers=roles['teacher'])
    assert response.status_code == 200, response.text
    q = response.json()
    body = {'name': '标准站考试', 'version_id': q['version_id'], 'classes': ['信号一班'],
            'opens_at': service.iso(clock[0]), 'closes_at': service.iso(clock[0] + timedelta(minutes=10)), 'duration_minutes': 5}
    return roles, q, body


def create(client, course, **changes):
    roles, _, body = course
    response = client.post(ROOT, headers=roles['teacher'], json={**body, **changes})
    assert response.status_code == 200, response.text
    return response.json()


def publish(client, course, **changes):
    exam = create(client, course, **changes)
    response = client.post(f"{ROOT}/{exam['id']}/publish", headers=course[0]['teacher'], json={'revision': exam['revision']})
    assert response.status_code == 200, response.text
    return response.json()


def begin(client, roles, exam, role='student'):
    response = client.post(f"{ROOT}/{exam['id']}/begin", headers=roles[role], json={'fullscreen': True})
    assert response.status_code == 200, response.text
    return response.json()


def control(kind, at, event_id=None):
    return {'event_id': event_id or str(uuid4()), 'kind': kind, 'occurred_at': service.iso(at)}


def sync(client, roles, sid, fullscreen, events=()):
    response = client.post(f'{ROOT}/attempts/{sid}/sync', headers=roles['student'], json={'fullscreen': fullscreen, 'events': list(events)})
    assert response.status_code == 200, response.text
    return response.json()


def event(client, roles, sid, sequence=1, **values):
    payload = {'event_id': str(uuid4()), 'sequence': sequence, 'action': 'button', 'button_id': 'D3DA', **values}
    return client.post(f'{ROOT}/attempts/{sid}/events', headers=roles['student'], json=payload), payload


def test_open_boundaries_fullscreen_refusal_one_opportunity_and_earliest_deadline(client, course, clock, db_session):
    roles, _, body = course
    exam = publish(client, course, opens_at=service.iso(clock[0] + timedelta(seconds=1)))
    assert client.post(f"{ROOT}/{exam['id']}/begin", headers=roles['student'], json={'fullscreen': False}).status_code == 422
    assert db_session.query(ExamAttempt).count() == 0
    assert client.post(f"{ROOT}/{exam['id']}/begin", headers=roles['student'], json={'fullscreen': True}).status_code == 409
    clock[0] += timedelta(seconds=1)
    first = begin(client, roles, exam)
    assert first['deadline'] == service.iso(clock[0] + timedelta(minutes=5))
    clock[0] += timedelta(minutes=1)
    assert begin(client, roles, exam)['session_id'] == first['session_id']
    assert begin(client, roles, exam)['deadline'] == first['deadline']
    response = client.post(f"{ROOT}/attempts/{first['session_id']}/submit", headers=roles['student'], json={'expected_sequence': 0})
    assert response.status_code == 200
    assert begin(client, roles, exam)['status'] == 'submitted'
    assert db_session.query(ExamAttempt).count() == 1
    clock[0] = service.utc(datetime.fromisoformat(body['closes_at'])) - timedelta(seconds=10)
    peer = begin(client, roles, exam, 'peer')
    assert peer['deadline'] == body['closes_at']
    clock[0] += timedelta(seconds=10)
    fresh = publish(client, course, opens_at=body['opens_at'], closes_at=service.iso(clock[0] + timedelta(seconds=1)))
    clock[0] += timedelta(seconds=1)
    assert client.post(f"{ROOT}/{fresh['id']}/begin", headers=roles['student'], json={'fullscreen': True}).status_code == 409


def test_freezes_roster_identity_version_and_initial_conditions(client, course, clock, db_session):
    roles, q, _ = course
    exam = publish(client, course)
    student = db_session.scalar(select(User).where(User.username == 's5_student'))
    student.class_name = '转入班'; student.real_name = '新姓名'; db_session.commit()
    late = auth_headers(client, 's5_late', 'student')
    assert client.post(f"{ROOT}/{exam['id']}/begin", headers=late, json={'fullscreen': True}).status_code == 404
    v = db_session.get(OperationVersion, q['version_id'])
    original_prompt = v.prompt
    # Even an out-of-band source mutation cannot change the frozen published exam.
    v.prompt = '未来题干'; v.initial = {'interval_available': False, 'occupied_sections': []}; db_session.commit()
    item = begin(client, roles, exam)
    assert item['identity']['class_name'] == '信号一班' and item['identity']['real_name'] == 's5_student'
    assert item['question']['prompt'] == original_prompt and item['question']['initial']['interval_available'] is True
    roster = client.get(f"{ROOT}/{exam['id']}/participants", headers=roles['teacher']).json()
    assert roster['total'] == 2
    assert client.delete(f"{BASE}/questions/{q['id']}", headers=roles['teacher']).status_code == 409
    assert client.put(f"{ROOT}/{exam['id']}", headers=roles['teacher'], json={**course[2], 'revision': exam['revision']}).status_code == 409
    assert client.post(f"{ROOT}/{exam['id']}/withdraw", headers=roles['teacher'], json={'revision': exam['revision']}).status_code == 409
    assert client.delete(f"{ROOT}/{exam['id']}", headers=roles['teacher']).status_code == 405


def test_draft_missing_fields_revision_copy_withdraw_and_timezone_validation(client, course, db_session):
    roles, _, body = course
    empty = client.post(ROOT, headers=roles['teacher'], json={}).json()
    assert client.post(f"{ROOT}/{empty['id']}/publish", headers=roles['teacher'], json={'revision': 1}).status_code == 409
    assert client.post(ROOT, headers=roles['teacher'], json={**body, 'opens_at': '2030-01-02T12:00:00'}).status_code == 422
    assert client.post(ROOT, headers=roles['teacher'], json={**body, 'duration_minutes': 0}).status_code == 422
    assert client.post(ROOT, headers=roles['teacher'], json={**body, 'opens_at': body['closes_at']}).status_code == 422
    created = create(client, course, opens_at='2030-01-02T12:00:00+08:00')
    assert created['opens_at'] == body['opens_at']
    edited = client.put(f"{ROOT}/{created['id']}", headers=roles['teacher'], json={**body, 'revision': 1})
    assert edited.status_code == 200 and edited.json()['revision'] == 2
    assert client.put(f"{ROOT}/{created['id']}", headers=roles['teacher'], json={**body, 'revision': 1}).status_code == 409
    exam = publish(client, course)
    assert client.post(f"{ROOT}/{exam['id']}/publish", headers=roles['teacher'], json={'revision': 1}).json()['revision'] == exam['revision']
    withdrawn = client.post(f"{ROOT}/{exam['id']}/withdraw", headers=roles['teacher'], json={'revision': exam['revision']})
    assert withdrawn.status_code == 200 and withdrawn.json()['participant_count'] == 0
    assert db_session.query(ExamParticipant).filter_by(exam_id=exam['id']).count() == 0
    cloned = client.post(f"{ROOT}/{created['id']}/copy", headers=roles['teacher']).json()
    assert cloned['id'] != created['id'] and cloned['status'] == 'draft' and cloned['participant_count'] == 0


def test_first_exit_refresh_dedup_resume_then_second_exit(client, course, clock, db_session):
    roles, _, _ = course; item = begin(client, roles, publish(client, course)); sid = item['session_id']
    clock[0] += timedelta(seconds=10)
    out = control('exit', clock[0]); first = sync(client, roles, sid, False, [out])
    assert first['exit_count'] == 1
    assert sync(client, roles, sid, False, [out])['exited_at'] == first['exited_at']
    assert sync(client, roles, sid, False)['exit_count'] == 1
    assert event(client, roles, sid)[0].status_code == 409
    clock[0] += timedelta(seconds=59)
    restored = sync(client, roles, sid, True, [control('restore', clock[0])])
    assert restored['status'] == 'active' and restored['exit_count'] == 1
    assert restored['deadline'] == item['deadline']
    assert event(client, roles, sid)[0].status_code == 200
    clock[0] += timedelta(seconds=1)
    second = sync(client, roles, sid, False, [control('exit', clock[0])])
    assert second['status'] == 'submitted' and second['finish_reason'] == 'fullscreen_limit'
    assert second['exit_count'] == 2 and second['message'] == service.COMPLETED
    assert 'score' not in json.dumps(second)
    assert db_session.query(ExamControlEvent).count() == 3


@pytest.mark.parametrize('reason,exit_after,close_after', [('fullscreen_timeout', 0, 300), ('deadline', 0, 30), ('deadline', 0, 60)])
def test_exact_timeout_earlier_deadline_and_service_sweep(client, course, clock, reason, exit_after, close_after, db_session):
    roles = course[0]
    exam = publish(client, course, closes_at=service.iso(clock[0] + timedelta(seconds=close_after)))
    item = begin(client, roles, exam); sid = item['session_id']
    sync(client, roles, sid, False, [control('exit', clock[0])])
    clock[0] += timedelta(seconds=60)
    service.settle_all(db_session)  # no browser/request needed to settle
    row = db_session.get(ExamAttempt, sid)
    assert row.finish_reason == reason
    assert row.submitted_at == min(row.deadline, row.exited_at + timedelta(seconds=60))
    final = sync(client, roles, sid, True, [control('restore', clock[0])])
    assert final['status'] == 'submitted' and final['finish_reason'] == reason
    assert event(client, roles, sid)[0].status_code == 409


def test_offline_exit_replay_keeps_original_time_and_only_disconnect_does_not_count(client, course, clock):
    roles = course[0]; item = begin(client, roles, publish(client, course)); sid = item['session_id']
    clock[0] += timedelta(seconds=20)
    # Network-only outage: no fullscreen transition is invented.
    result = sync(client, roles, sid, True)
    assert result['exit_count'] == 0 and result['deadline'] == item['deadline']
    out = control('exit', clock[0]); clock[0] += timedelta(seconds=61)
    replay = sync(client, roles, sid, False, [out])
    assert replay['finish_reason'] == 'fullscreen_timeout'
    assert replay['submitted_at'] == service.iso(datetime.fromisoformat(out['occurred_at']).replace(tzinfo=None) + timedelta(seconds=60))


def test_offline_exit_restore_replay_then_refresh_and_id_content_conflict(client, course, clock):
    roles = course[0]; item = begin(client, roles, publish(client, course)); sid = item['session_id']
    clock[0] += timedelta(seconds=5); out = control('exit', clock[0])
    clock[0] += timedelta(seconds=30); back = control('restore', clock[0])
    clock[0] += timedelta(seconds=40)
    item = sync(client, roles, sid, True, [out, back])
    assert item['status'] == 'active' and item['exit_count'] == 1
    assert sync(client, roles, sid, True, [out, back])['exit_count'] == 1
    altered = {**out, 'kind': 'restore'}
    assert client.post(f'{ROOT}/attempts/{sid}/sync', headers=roles['student'], json={'fullscreen': True, 'events': [altered]}).status_code == 409
    assert sync(client, roles, sid, False)['finish_reason'] == 'fullscreen_limit'


def test_sealed_log_idempotent_retries_pending_sequence_and_program_exit(client, course, clock, db_session):
    roles = course[0]; item = begin(client, roles, publish(client, course)); sid = item['session_id']
    response, payload = event(client, roles, sid)
    assert response.status_code == 200
    submit_path = f'{ROOT}/attempts/{sid}/submit'
    assert client.post(submit_path, headers=roles['student'], json={'expected_sequence': 0}).status_code == 409
    assert client.post(submit_path, headers=roles['student'], json={'expected_sequence': 1}).json()['status'] == 'submitted'
    clock[0] += timedelta(seconds=5)
    result = sync(client, roles, sid, False, [control('exit', clock[0])])
    assert result['exit_count'] == 0 and result['finish_reason'] == 'manual'
    assert client.post(submit_path, headers=roles['student'], json={'expected_sequence': 1}).json()['submitted_at'] == result['submitted_at']
    assert client.post(f'{ROOT}/attempts/{sid}/events', headers=roles['student'], json=payload).status_code == 200
    assert event(client, roles, sid, 2)[0].status_code == 409
    assert db_session.query(OperationEvent).filter_by(session_id=sid).count() == 1


def test_late_action_seals_at_deadline_and_does_not_append(client, course, clock, db_session):
    roles = course[0]; item = begin(client, roles, publish(client, course)); sid = item['session_id']
    assert event(client, roles, sid)[0].status_code == 200
    clock[0] += timedelta(minutes=5)
    assert event(client, roles, sid, 2)[0].status_code == 409
    assert db_session.get(ExamAttempt, sid).finish_reason == 'deadline'
    assert db_session.query(OperationEvent).filter_by(session_id=sid).count() == 1


def test_permissions_no_learning_or_authoring_bypass_no_student_answers_or_grades(client, course, db_session):
    roles, q, _ = course; exam = publish(client, course); item = begin(client, roles, exam); sid = item['session_id']
    other = auth_headers(client, 's5_other_teacher', 'teacher')
    assert client.get(ROOT, headers=other).json()['total'] == 0
    for auth in [other, roles['peer']]:
        for suffix in ['', '/log.json']:
            assert client.get(f'{ROOT}/attempts/{sid}{suffix}', headers=auth).status_code == 404
    assert client.get(f'{ROOT}/{exam["id"]}', headers=other).status_code == 404
    for suffix in ['', '/log.json']:
        assert client.get(f'{BASE}/sessions/{sid}{suffix}', headers=roles['teacher']).status_code == 404
    assert client.post(f'{BASE}/sessions/{sid}/stop', headers=roles['teacher']).status_code == 404
    assert client.get(f'/api/operation-learning/attempts/{sid}', headers=roles['student']).status_code == 404
    assert client.get(f'{ROOT}/attempts/{sid}/log.json', headers=roles['student']).status_code == 409
    assert client.post(f'{ROOT}/attempts/{sid}/submit', headers=roles['student'], json={'expected_sequence': 0, 'score': 100}).status_code == 422
    client.post(f'{ROOT}/attempts/{sid}/submit', headers=roles['student'], json={'expected_sequence': 0})
    for path in [f'{ROOT}/attempts/{sid}', f'{ROOT}/attempts/{sid}/log.json', ROOT, ROOT + '/history']:
        response = client.get(path, headers=roles['student'])
        assert response.status_code == 200, response.text
        for forbidden in ['standard_log', 'standard_session_id', 'automatic_evaluation', 'score', 'ai_text', 'outcome']:
            assert forbidden not in response.text
    assert client.get(f'{ROOT}/attempts/{sid}', headers=roles['admin']).json()['automatic_evaluation'] is None
    assert client.get(f'{ROOT}/attempts/{sid}', headers=roles['teacher']).json()['question']['standard_log']
    assert client.get(f'{ROOT}/attempts/{sid}/log.json', headers=roles['teacher']).status_code == 200


def test_multiple_current_exams_and_six_item_history(client, course, db_session, clock):
    roles = course[0]
    exams = [publish(client, course, name=f'考试 {i}') for i in range(8)]
    listing = client.get(ROOT, headers=roles['student']).json()
    assert listing['total'] == 8 and len(listing['items']) == 6
    assert len(client.get(ROOT + '?page=2', headers=roles['student']).json()['items']) == 2
    for exam in exams:
        item = begin(client, roles, exam)
        client.post(f"{ROOT}/attempts/{item['session_id']}/submit", headers=roles['student'], json={'expected_sequence': 0})
        clock[0] += timedelta(seconds=1)
    first = client.get(ROOT + '/history', headers=roles['student']).json()
    second = client.get(ROOT + '/history?page=2', headers=roles['student']).json()
    assert first['total'] == 8 and len(first['items']) == 6 and len(second['items']) == 2
    assert first['items'][0]['exam_id'] == exams[-1]['id']
    assert len(client.get(ROOT, headers=roles['teacher']).json()['items']) == 6


def test_unified_student_list_contains_open_active_upcoming_and_ended_exams(client, course, clock):
    roles = course[0]
    opened = publish(client, course, name='可参加')
    upcoming = publish(client, course, name='未开始', opens_at=service.iso(clock[0]+timedelta(minutes=5)))
    expired = publish(client, course, name='已截止', closes_at=service.iso(clock[0]+timedelta(minutes=1)))
    completed = publish(client, course, name='已交卷')
    sid = begin(client, roles, completed)['session_id']
    client.post(f'{ROOT}/attempts/{sid}/submit', headers=roles['student'], json={'expected_sequence':0})
    active = publish(client, course, name='进行中')
    begin(client, roles, active)
    clock[0] += timedelta(minutes=2)
    listing = client.get(ROOT, headers=roles['student']).json()
    assert listing['total'] == 5
    by_id = {row['id']:row for row in listing['items']}
    assert [row['state'] for row in listing['items'][:3]] == ['active','open','upcoming']
    for exam, state in [(opened,'open'),(active,'active'),(upcoming,'upcoming'),(expired,'missed'),(completed,'submitted')]:
        assert by_id[exam['id']]['state'] == state
    assert by_id[completed['id']]['attempt']['session_id'] == sid
    assert 'standard_log' not in json.dumps(listing)


def test_cross_connection_concurrent_begin_submit_and_restart_catchup(client, course, clock, db_session):
    roles = course[0]; exam = publish(client, course)
    factory = sessionmaker(bind=db_session.get_bind())
    uid = db_session.scalar(select(User.id).where(User.username == 's5_student'))
    def start():
        with factory() as db, service.atomic(db):
            return service.begin(db, db.get(User, uid), exam['id'], True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start(), range(2)))
    assert results[0]['session_id'] == results[1]['session_id']
    sid = results[0]['session_id']
    def submit():
        with factory() as db, service.atomic(db):
            return service.submit(db, db.get(User, uid), sid, 0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        submitted = list(pool.map(lambda _: submit(), range(2)))
    assert submitted[0]['submitted_at'] == submitted[1]['submitted_at']
    db_session.expire_all()
    assert db_session.query(ExamAttempt).count() == 1
    second = begin(client, roles, publish(client, course, name='重启结算'))
    clock[0] += timedelta(minutes=20)
    # A new session simulates process restart without carrying runtime state in memory.
    with factory() as db:
        service.settle_all(db)
    db_session.expire_all()
    row = db_session.get(ExamAttempt, second['session_id'])
    assert row.finish_reason == 'deadline' and service.iso(row.submitted_at) == second['deadline']


def test_real_background_clock_and_restart_preserve_original_due_time(client, course, clock, db_session, monkeypatch):
    import asyncio
    import main
    roles = course[0]; item = begin(client, roles, publish(client, course)); sid = item['session_id']
    assert event(client, roles, sid)[0].status_code == 200
    factory = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr(main, 'SessionLocal', factory)
    monkeypatch.setattr(main, 'engine', db_session.get_bind())
    clock[0] += timedelta(minutes=6)
    async def run_clock():
        await main.start_exam_clock()
        try:
            await asyncio.sleep(1.3)
        finally:
            await main.stop_exam_clock()
    asyncio.run(run_clock())
    db_session.expire_all()
    row = db_session.get(ExamAttempt, sid)
    assert row.finish_reason == 'deadline' and service.iso(row.submitted_at) == item['deadline']
    assert db_session.query(OperationEvent).filter_by(session_id=sid).count() == 1
    main.on_startup()  # startup catch-up is wired to the same persisted exam state
    db_session.expire_all()
    assert db_session.get(ExamAttempt, sid).revision == row.revision


def test_concurrent_deadline_and_manual_submit_have_one_deterministic_reason(client, course, clock, db_session):
    roles = course[0]; item = begin(client, roles, publish(client, course)); sid = item['session_id']
    uid = db_session.scalar(select(User.id).where(User.username == 's5_student'))
    factory = sessionmaker(bind=db_session.get_bind())
    clock[0] += timedelta(minutes=5)
    def submit():
        with factory() as db, service.atomic(db):
            return service.submit(db, db.get(User, uid), sid, 0)
    def sweep():
        with factory() as db:
            service.settle_all(db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(submit); b = pool.submit(sweep)
        result = a.result(); b.result()
    db_session.expire_all()
    row = db_session.get(ExamAttempt, sid)
    assert result['finish_reason'] == row.finish_reason == 'deadline'
    assert row.revision == 1
