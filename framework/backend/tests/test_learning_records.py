"""Learning records expose real evidence and never cross account boundaries."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.core.security import create_access_token
from app.models.user import User
from app.models.module_one import ModuleOneAttempt
from app.services.module_one import repository as repo
from app.api import interlocking_exam, simulation_console
from tests.test_lab_topics import topics, completed


@pytest.fixture()
def accounts(db_session):
    users = [User(username=f'record_{role}', password_hash='unused', role=role)
             for role in ('student', 'teacher', 'admin')]
    db_session.add_all(users)
    db_session.commit()
    return users


def headers(user):
    return {'Authorization': f"Bearer {create_access_token({'sub': str(user.id)})}"}


def test_dynamic_owner_isolation_and_running_exam_has_no_rubric(client, db_session, accounts):
    student, teacher, admin = accounts
    attempt = repo.create_attempt(db_session, student, 'E1-1-1', 'E1-1-1', 'exam')
    aid = attempt['attempt_id']
    response = repo.apply_command(db_session, db_session.get(ModuleOneAttempt, aid), {
        'command_id': str(uuid4()), 'expected_version': 0,
        'type': 'SWITCH_TOTAL_REVERSE', 'target': '5/7', 'payload': {},
    })
    result = client.get(f'/api/learning-records/dynamic/{aid}', headers=headers(student))
    assert result.status_code == 200
    detail = result.json()
    assert detail['operation_count'] == 1
    assert detail['operations'][0]['accepted'] == response['accepted']
    assert detail['score'] is None and detail['errors'] == []
    assert 'checkpoints' not in result.text and 'route_definitions' not in result.text
    for account in (teacher, admin):
        assert client.get('/api/learning-records', headers=headers(account)).json()['total'] == 0
        assert client.get(f'/api/learning-records/dynamic/{aid}', headers=headers(account)).status_code == 404
    submitted = repo.submit_attempt(db_session, db_session.get(ModuleOneAttempt, aid), 1, '')
    detail = client.get(f'/api/learning-records/dynamic/{aid}', headers=headers(student)).json()
    assert detail['score'] == submitted['result']['score']
    assert detail['errors'] and detail['errors'][0]['correction']


def test_expected_refusal_dynamic_checkpoint_is_not_a_student_error(client, db_session, accounts):
    student = accounts[0]
    attempt = repo.create_attempt(db_session, student, 'E1-1-2-0', 'E1-1-2-0', 'practice')
    aid, version = attempt['attempt_id'], 0
    for kind in ('SWITCH_SINGLE_LOCK', 'SWITCH_TOTAL_NORMAL', 'SWITCH_TOTAL_REVERSE',
                 'SWITCH_SINGLE_UNLOCK', 'SWITCH_TOTAL_REVERSE', 'SWITCH_TOTAL_NORMAL'):
        result = repo.apply_command(db_session, db_session.get(ModuleOneAttempt, aid), {
            'command_id': str(uuid4()), 'expected_version': version, 'type': kind, 'target': '9/11', 'payload': {}})
        version = result['after_version']
    repo.submit_attempt(db_session, db_session.get(ModuleOneAttempt, aid), version, '')
    detail = client.get(f'/api/learning-records/dynamic/{aid}', headers=headers(student)).json()
    assert detail['score'] == 100
    assert any(op['accepted'] is False for op in detail['operations'])
    assert detail['error_count'] == 0 and detail['errors'] == []


def test_console_is_durable_without_poll_operations_or_pin(client, db_session, accounts):
    user = accounts[0]
    auth = headers(user)
    created = client.post('/api/simulation-console/sessions', headers=auth, json={'source': 'reference'})
    assert created.status_code == 200
    sid = created.json()['session_id']
    client.get(f'/api/simulation-console/sessions/{sid}', headers=auth)
    rejected = client.post(f'/api/simulation-console/sessions/{sid}/commands', headers=auth,
                          json={'type': 'SIGNAL_SEAL', 'target': 'X', 'pin': 'private-test-pin',
                                'payload': {'pin': 'also-private'}})
    assert rejected.status_code == 200 and rejected.json()['accepted'] is False
    client.post(f'/api/simulation-console/sessions/{sid}/clear-selection', headers=auth, json={})
    listing = client.get('/api/learning-records?kind=simulation', headers=auth)
    assert listing.status_code == 200
    item = listing.json()['items'][0]
    assert item['operation_count'] == 2 and item['score'] is None
    assert '未评分' in item['score_label']
    simulation_console.reference_service.sessions.pop(sid)
    detail_response = client.get(f"/api/learning-records/simulation/{item['record_id']}", headers=auth)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail['operations']) == 2 and detail['operations'][0]['accepted'] is False
    assert detail['feedback'][0]['source'] == 'rules'
    assert detail['snapshots']
    from app.models.learning_archive import LearningArchive, LearningArchiveEvent
    persisted = repr([(a.data, a.initial_snapshot, a.latest_snapshot) for a in db_session.query(LearningArchive)])
    persisted += repr([(e.command, e.response) for e in db_session.query(LearningArchiveEvent)])
    assert 'private-test-pin' not in persisted and 'also-private' not in persisted


def test_student_free_practice_is_recorded_only_on_owned_session(client, accounts):
    user, teacher, _ = accounts
    sid = client.post('/api/simulation-console/sessions', headers=headers(user), json={}).json()['session_id']
    response = client.post(f'/api/simulation-console/sessions/{sid}/commands', headers=headers(user),
                          json={'type': 'SET_SECTION_OCCUPANCY', 'target': '7DG', 'payload': {'kind': 'fault'}})
    assert response.status_code == 200 and response.json()['accepted']
    detail = client.get(f'/api/learning-records/simulation/{sid}', headers=headers(user)).json()
    assert detail['operation_count'] == 1 and detail['operations'][0]['accepted'] is True
    assert detail['errors'] == []
    foreign = client.post(f'/api/simulation-console/sessions/{sid}/commands', headers=headers(teacher),
                          json={'type': 'SET_SECTION_OCCUPANCY', 'target': '7DG'})
    assert foreign.status_code == 409
    assert client.get('/api/learning-records', headers=headers(teacher)).json()['total'] == 0


def test_classic_submission_and_explanation_are_bound_to_owned_answer(client, db_session, accounts, monkeypatch):
    user, _, admin = accounts
    answer = {'route_type': 'dongjiao_to_III', 'route_buttons': ['XDLA']}
    result = client.post('/api/exam/submit', headers=headers(user), json=answer)
    assert result.status_code == 200
    rid = result.json().get('record_id')
    assert rid
    monkeypatch.setattr(interlocking_exam, '_call_ai_for_explanation', lambda *a, **k: {
        'ai_explanation': '本地规则说明', 'source': 'rules_fallback', 'items': []})
    req = {**answer, 'record_id': rid}
    assert client.post('/api/exam/ai-explain', headers=headers(admin), json=req).status_code == 404
    assert client.post('/api/exam/ai-explain', headers=headers(user), json={**req, 'route_buttons': []}).status_code == 409
    assert client.post('/api/exam/ai-explain', headers=headers(user), json=req).status_code == 200
    detail = client.get(f'/api/learning-records/classic/{rid}', headers=headers(user)).json()
    assert detail['score'] is None and detail['status'] == 'submitted'
    assert detail['error_count'] > 0
    assert any(f['source'] == 'rules_fallback' and f['text'] == '本地规则说明' for f in detail['feedback'])
    assert client.post('/api/exam/ai-explain', headers=headers(user), json=answer).status_code == 200
    assert client.get('/api/learning-records', headers=headers(user)).json()['total'] == 1


def test_list_pagination_filters_and_preview(client, accounts):
    teacher = accounts[1]
    for _ in range(3):
        client.post('/api/exam/submit', headers=headers(teacher), json={})
    payload = client.get('/api/learning-records?kind=classic&page=2&limit=2', headers=headers(teacher)).json()
    assert payload['total'] == 3 and len(payload['items']) == 1
    assert payload['counts']['all'] == 3 and payload['counts']['classic'] == 3
    assert payload['items'][0]['preview'] is True
    assert client.get('/api/learning-records?kind=bogus', headers=headers(teacher)).status_code == 422
    assert client.get('/api/learning-records?page=0', headers=headers(teacher)).status_code == 422


def test_lab_preserves_real_grades_errors_and_teacher_feedback(client, db_session, accounts, topics):
    from app.models.lab_topic import LabAttempt
    from app.services.lab_topics import evaluate
    from app.services.grading import save_grade, grade_etag
    question = topics[0]
    answers = completed(question)
    result = evaluate(question.content, answers)
    attempt = LabAttempt(question_id=question.id, student_id=accounts[0].id,
                         question_snapshot=deepcopy(question.content), answers=answers, result=result)
    db_session.add(attempt)
    db_session.commit()
    url = f'/api/learning-records/lab/{attempt.id}'
    pending = client.get(url, headers=headers(accounts[0])).json()
    assert pending['score'] is None and pending['score_max'] == result['total_max']
    manual = {f['id']: f for f in question.content['fields'] if f['kind'] == 'essay'}
    fid = next(iter(manual))
    raw = {'scores': {key: 0 for key in manual}, 'comment': '请补充实验现象的依据。',
           'field_comments': {fid: '应区分观测现象与推断。'},
           'rubric_scores': {key: {r['id']: 0 for r in field.get('rubric', [])} for key, field in manual.items()}}
    save_grade(db_session, attempt, accounts[1].id, raw, grade_etag(attempt))
    db_session.commit()
    detail = client.get(url, headers=headers(accounts[0])).json()
    assert detail['score'] == result['automatic_score']
    assert any(f['source'] == 'teacher' and f['text'] == raw['comment'] for f in detail['feedback'])
    assert any(f['source'] == 'teacher' and f['text'] == raw['field_comments'][fid] for f in detail['feedback'])
    for account in accounts[1:]:
        assert client.get(url, headers=headers(account)).status_code == 404


def test_legacy_aggregates_actual_operation_and_rule_score(client, db_session, accounts, seeded_station):
    from datetime import datetime, timezone
    from app.models.exercise import Exercise
    from app.models.exercise_session import ExerciseSession
    from app.models.operation_log import OperationLog
    from app.models.ai_score import AiScore
    exercise = Exercise(teacher_id=accounts[1].id, station_id=seeded_station, title='实际教学任务')
    db_session.add(exercise)
    db_session.flush()
    attempt = ExerciseSession(student_id=accounts[0].id, exercise_id=exercise.id, station_id=seeded_station,
                              start_time=datetime.now(timezone.utc), status='completed')
    db_session.add(attempt)
    db_session.flush()
    db_session.add(OperationLog(session_id=attempt.id, sequence_no=1, operation_type='switch', target_code='W1',
                               target_type='switch', operation_result='failed', error_message='区段占用'))
    db_session.add(AiScore(session_id=attempt.id, total_score=73, ai_comment='本地评分意见',
                           suggestions=['先检查占用状态'], deepseek_response={'mode': 'deepseek_placeholder'}))
    db_session.commit()
    url = f'/api/learning-records/legacy/{attempt.id}'
    detail = client.get(url, headers=headers(accounts[0])).json()
    assert detail['score'] == 73 and detail['score_max'] == 100
    assert detail['operations'][0]['accepted'] is False
    assert detail['errors'][0]['message'] == '区段占用'
    assert detail['feedback'][0]['source'] == 'rules_fallback'
    assert client.get(url, headers=headers(accounts[2])).status_code == 404
