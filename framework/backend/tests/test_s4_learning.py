"""S4 real HTTP/SQLite contracts with deterministic AI substitutes only."""
import copy
import json
from uuid import uuid4
import pytest
from app.models import User
from app.models.operation import OperationSession
from app.models.operation_learning import OperationAttempt, OperationReview
from app.services.operation_comparison import compare
from app.services import operation_explanation as ai
from tests.helpers import auth_headers
from tests.test_s3_operations import BASE, draft, record_standard

ROOT = '/api/operation-learning'


@pytest.fixture()
def course(client):
    roles = {role: auth_headers(client, 's4_' + role, role) for role in ('student', 'teacher', 'admin')}
    roles['peer'] = auth_headers(client, 's4_peer', 'student')
    roles['other_teacher'] = auth_headers(client, 's4_other_teacher', 'teacher')
    q = draft(client, roles['teacher'])
    q, recording = record_standard(client, roles['teacher'], q['id'])
    assert client.post(f"{BASE}/questions/{q['id']}/publish", headers=roles['teacher']).status_code == 200
    return roles, q, recording


def begin(client, roles, q, **body):
    response = client.post(f"{ROOT}/questions/{q['id']}/begin", headers=roles['student'], json=body)
    assert response.status_code == 200, response.text
    return response.json()


def event(client, auth, sid, sequence, **values):
    payload = {'event_id': str(uuid4()), 'sequence': sequence, 'action': 'button', 'button_id': 'D3DA', **values}
    return client.post(f'{ROOT}/attempts/{sid}/events', headers=auth, json=payload), payload


def submit(client, auth, sid):
    response = client.post(f'{ROOT}/attempts/{sid}/submit', headers=auth, json={})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('variant', ['same', 'missing', 'extra', 'order', 'parameters'])
def test_strict_comparison_ignores_random_metadata_and_results(variant):
    expected = [{'action': 'button', 'button_id': b, 'target_id': b[:-2], 'parameters': {'a': 1, 'b': 2},
                 'event_id': str(uuid4()), 'session_id': 'recording', 'event_time': 'old'} for b in ['D3DA', 'D7DA']]
    actual = copy.deepcopy(expected)
    for item in actual:
        item.update(event_id=str(uuid4()), session_id='student', event_time='new', result={'accepted': False})
        item['parameters'] = {'b': 2, 'a': 1}
    if variant == 'missing': actual.pop()
    if variant == 'extra': actual.insert(0, copy.deepcopy(actual[0]))
    if variant == 'order': actual.reverse()
    if variant == 'parameters': actual[1]['parameters']['a'] = 2
    result = compare(expected, actual)
    assert result['score'] == (100 if variant == 'same' else None)
    assert result['status'] == ('correct' if variant == 'same' else 'error')
    assert (result['first_difference'] is None) == (variant == 'same')


def test_answer_secrecy_resume_isolation_retry_and_sealing(client, course, db_session):
    roles, q, recording = course
    attempt = begin(client, roles, q)
    sid = attempt['session_id']
    assert 'standard_log' not in json.dumps(attempt)
    assert recording['session_id'] not in json.dumps(attempt)
    assert begin(client, roles, q)['session_id'] == sid
    for suffix in ['', '/console', '/log.json']:
        assert client.get(f'{ROOT}/attempts/{sid}{suffix}', headers=roles['peer']).status_code == 404
    assert client.get(f'{ROOT}/attempts/{sid}/log.json', headers=roles['student']).status_code == 409
    assert client.get(f'{BASE}/sessions/{sid}', headers=roles['student']).status_code == 403
    assert client.post(f'{ROOT}/attempts/{sid}/explanation', headers=roles['student'], json={}).status_code == 409
    response, payload = event(client, roles['student'], sid, 1)
    assert response.status_code == 200, response.text
    retried = client.post(f'{ROOT}/attempts/{sid}/events', headers=roles['student'], json=payload)
    assert retried.json()['revision'] == 1
    restored = client.get(f'{ROOT}/attempts/{sid}/console', headers=roles['student']).json()
    assert restored['snapshot']['selected_buttons'] == ['D3DA']
    peer = begin(client, {**roles, 'student': roles['peer']}, q)
    assert peer['console']['events'] == [] and peer['console']['snapshot']['selected_buttons'] == []
    response, _ = event(client, roles['student'], sid, 2, button_id='D7DA')
    assert response.status_code == 200
    result = submit(client, roles['student'], sid)
    assert result['outcome']['score'] == 100
    assert result['question']['standard_log'] == q['standard_log']
    assert submit(client, roles['student'], sid)['outcome'] == result['outcome']
    assert event(client, roles['student'], sid, 3)[0].status_code == 409
    assert client.post(f'{ROOT}/attempts/{sid}/events', headers=roles['student'], json=payload).status_code == 200
    assert client.get(f'{ROOT}/attempts/{sid}/log.json', headers=roles['student']).status_code == 200
    assert client.get(f'{ROOT}/attempts/{sid}/log.json', headers=roles['peer']).status_code == 404
    assert db_session.get(OperationAttempt, sid).outcome['score'] == 100


def test_real_duplicate_rejected_target_and_restart_are_preserved(client, course, db_session):
    roles, q, _ = course
    first = begin(client, roles, q)
    sid = first['session_id']
    for sequence in [1, 2]:
        assert event(client, roles['student'], sid, sequence)[0].status_code == 200
    bad, _ = event(client, roles['student'], sid, 3, action='target', button_id=None,
                   target_id='1', target_kind='switch')
    assert bad.status_code == 200 and bad.json()['event']['result']['accepted'] is False
    second = begin(client, roles, q, restart_from=sid)
    assert second['session_id'] != sid and second['console']['events'] == []
    assert second['console']['pending'] is None
    assert begin(client, roles, q, restart_from=sid)['session_id'] == second['session_id']
    assert db_session.get(OperationSession, sid).status == 'abandoned'
    assert len(client.get(f'{ROOT}/attempts/{sid}', headers=roles['student']).json()['console']['events']) == 3
    assert 'standard_log' not in json.dumps(client.get(f'{ROOT}/attempts/{sid}', headers=roles['student']).json())
    assert client.post(f'{ROOT}/attempts/{sid}/submit', headers=roles['student'], json={}).status_code == 409
    result = submit(client, roles['student'], second['session_id'])
    assert result['outcome']['status'] == 'error' and result['outcome']['score'] is None
    assert result['outcome']['first_difference']['sequence'] == 1


def test_classes_version_snapshot_disable_and_delete_protection(client, course, db_session):
    roles, q, _ = course
    attempt = begin(client, roles, q)
    sid = attempt['session_id']
    original = copy.deepcopy(db_session.get(OperationAttempt, sid).question_snapshot)
    updated = client.get(f"{BASE}/questions/{q['id']}", headers=roles['teacher']).json()
    body = {key: updated[key] for key in ('title', 'prompt', 'classes', 'initial', 'revision')}
    body.update(title='版本二', classes=['信号二班'])
    assert client.put(f"{BASE}/questions/{q['id']}", headers=roles['teacher'], json=body).status_code == 200
    record_standard(client, roles['teacher'], q['id'])
    assert client.post(f"{BASE}/questions/{q['id']}/publish", headers=roles['teacher']).status_code == 200
    submit(client, roles['student'], sid)
    assert db_session.get(OperationAttempt, sid).question_snapshot == original
    assert client.delete(f"{BASE}/questions/{q['id']}", headers=roles['teacher']).status_code == 409
    other = db_session.query(User).filter_by(username='s4_peer').one()
    other.class_name = '未发布班级'; db_session.commit()
    assert client.post(f"{ROOT}/questions/{q['id']}/begin", headers=roles['peer'], json={}).status_code == 404
    student = db_session.query(User).filter_by(username='s4_student').one()
    student.class_name = '信号二班'; db_session.commit()
    active = begin(client, roles, q)
    client.post(f"{BASE}/questions/{q['id']}/disable", headers=roles['teacher'])
    assert begin(client, roles, q)['session_id'] == active['session_id']
    assert submit(client, roles['student'], active['session_id'])['status'] == 'submitted'
    assert client.post(f"{ROOT}/questions/{q['id']}/begin", headers=roles['student'], json={}).status_code == 404


def test_shared_review_revision_and_payload_boundaries(client, course, db_session):
    roles, q, _ = course
    sid = begin(client, roles, q)['session_id']
    submit(client, roles['student'], sid)
    path = f'{ROOT}/attempts/{sid}/review'
    assert client.put(path, headers=roles['student'], json={'revision': 0}).status_code == 403
    for wrong in [{'scores': {}}, {'score': 30}, {'answers': {}}, {'outcome': {'score': 100}}]:
        assert client.put(path, headers=roles['teacher'], json={'revision': 0, **wrong}).status_code == 422
        assert client.post(f'{ROOT}/attempts/{sid}/submit', headers=roles['student'], json=wrong).status_code == 422
    response = client.put(path, headers=roles['teacher'], json={'revision': 0, 'comment': '请按顺序操作', 'confirmed': True})
    assert response.status_code == 200, response.text
    assert client.get(f'{ROOT}/attempts/{sid}', headers=roles['other_teacher']).json()['review']['comment'] == '请按顺序操作'
    assert client.put(path, headers=roles['other_teacher'], json={'revision': 0}).status_code == 409
    assert client.put(path, headers=roles['other_teacher'], json={'revision': 1, 'comment': '已复核'}).status_code == 200
    assert len(db_session.get(OperationReview, sid).audit) == 2
    downloaded = client.get(f'{ROOT}/attempts/{sid}/log.json', headers=roles['student'])
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.json()['review']['comment'] == '已复核'
    assert client.get(ROOT + '/attempts', headers=roles['other_teacher']).json()['total'] == 1
    assert client.get(ROOT + '/attempts?class_name=不存在', headers=roles['teacher']).json()['total'] == 0
    assert client.get(ROOT + '/attempts?student_number=peer', headers=roles['teacher']).json()['total'] == 0
    assert client.post(f'{BASE}/sessions/{sid}/stop', headers=roles['teacher']).status_code == 404


@pytest.mark.parametrize('mode,status', [('success', 'ready'), ('missing', 'unconfigured'),
                                       ('timeout', 'timeout'), ('invalid', 'invalid_response'), ('error', 'service_error')])
def test_ai_substitutes_never_change_results_or_leak_secrets(client, course, db_session, monkeypatch, mode, status):
    roles, q, _ = course
    sid = begin(client, roles, q)['session_id']
    result = submit(client, roles['student'], sid)['outcome']
    monkeypatch.setattr(ai.settings, 'deepseek_api_key', None if mode == 'missing' else 'test-provider-secret')
    seen = []
    def provider(payload):
        seen.append(json.dumps(payload, ensure_ascii=False))
        if mode == 'timeout': raise TimeoutError('secret exception')
        if mode == 'error': raise ValueError('test-provider-secret')
        return '首个操作缺失，请按标准顺序操作。' if mode == 'success' else None
    monkeypatch.setattr(ai, 'provider', provider)
    for _ in range(2):
        response = client.post(f'{ROOT}/attempts/{sid}/explanation', headers=roles['student'], json={})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['outcome'] == result and data['ai_status'] == status
        assert (data['ai_text'] is not None) == (mode == 'success')
        assert 'test-provider-secret' not in response.text and 'secret exception' not in response.text
    for context in seen:
        for secret in ['password_hash', 'password123', 'access_token', 'test-provider-secret', 's4_student', 'real_name']:
            assert secret not in context
    assert db_session.query(OperationAttempt).count() == 1


def test_learning_and_teacher_lists_paginate_by_six_without_exposing_other_students(client, course):
    roles, q, _ = course
    ids = []
    for _ in range(7):
        sid = begin(client, roles, q)['session_id']
        ids.append(sid)
        submit(client, roles['student'], sid)
    for role in ['student', 'teacher', 'other_teacher', 'admin']:
        first = client.get(ROOT + '/attempts?page=1', headers=roles[role]).json()
        second = client.get(ROOT + '/attempts?page=2', headers=roles[role]).json()
        assert first['total'] == second['total'] == 7
        assert first['page_size'] == 6 and len(first['items']) == 6 and len(second['items']) == 1
        assert {row['session_id'] for row in first['items'] + second['items']} == set(ids)
    assert client.get(ROOT + '/attempts', headers=roles['peer']).json()['total'] == 0
    assert client.get(ROOT + '/attempts?question_search=不存在', headers=roles['teacher']).json()['total'] == 0


def test_teacher_recording_history_does_not_mix_student_attempts_and_release_order_is_current(client, course):
    roles, q, recording = course
    sid = begin(client, roles, q)['session_id']
    history = client.get(f"{BASE}/questions/{q['id']}", headers=roles['teacher']).json()['sessions']
    assert sid not in [item['id'] for item in history]
    assert recording['session_id'] in [item['id'] for item in history]
    q2 = draft(client, roles['teacher'], title='较早发布')
    record_standard(client, roles['teacher'], q2['id'])
    client.post(f"{BASE}/questions/{q2['id']}/publish", headers=roles['teacher'])
    current = client.get(f"{BASE}/questions/{q['id']}", headers=roles['teacher']).json()
    body = {key: current[key] for key in ('title', 'prompt', 'classes', 'initial', 'revision')}
    client.put(f"{BASE}/questions/{q['id']}", headers=roles['teacher'], json=body)
    record_standard(client, roles['teacher'], q['id'])
    client.post(f"{BASE}/questions/{q['id']}/publish", headers=roles['teacher'])
    items = client.get(BASE + '/questions', headers=roles['student']).json()['items']
    assert [row['id'] for row in items] == [q['id'], q2['id']]


def test_former_student_with_teacher_role_can_read_own_old_learning_session_without_operating_it(client, course, db_session):
    roles, q, _ = course
    sid = begin(client, roles, q)['session_id']
    user = db_session.query(User).filter_by(username='s4_student').one()
    user.role = 'teacher'; db_session.commit()
    result = client.get(f'{ROOT}/attempts/{sid}', headers=roles['student'])
    assert result.status_code == 200, result.text
    assert result.json()['console']['read_only'] is True
    assert client.post(f'{BASE}/sessions/{sid}/stop', headers=roles['student']).status_code == 404


def test_ai_crash_lease_and_late_response_cannot_override_a_new_generation(client, course, db_session, monkeypatch):
    from datetime import timedelta
    from sqlalchemy import update
    from app.services.operation_learning import now
    roles, q, _ = course
    sid = begin(client, roles, q)['session_id']
    submit(client, roles['student'], sid)
    item = db_session.get(OperationAttempt, sid)
    item.ai_status = 'generating'; item.ai_token = 'crashed-worker'; item.ai_started_at = now()
    db_session.commit()
    monkeypatch.setattr(ai.settings, 'deepseek_api_key', 'fake-only')
    def replaced_worker(payload):
        db_session.execute(update(OperationAttempt).where(OperationAttempt.session_id == sid).values(
            ai_token='new-worker', ai_status='ready', ai_text='保留新讲解'))
        db_session.commit()
        return '旧请求迟到的讲解'
    monkeypatch.setattr(ai, 'provider', replaced_worker)
    # A valid concurrent lease returns the current state without calling a provider.
    first = client.post(f'{ROOT}/attempts/{sid}/explanation', headers=roles['student'], json={}).json()
    assert first['ai_status'] == 'generating' and first['ai_text'] is None
    item.ai_started_at = now() - timedelta(seconds=61); db_session.commit()
    recovered = client.post(f'{ROOT}/attempts/{sid}/explanation', headers=roles['student'], json={}).json()
    assert recovered['ai_text'] == '保留新讲解'
    assert recovered['outcome']['score'] is None


@pytest.mark.parametrize('choice', [None, 'length', 'empty', 'valid'])
def test_provider_validates_complete_output_and_uses_bounded_requests(monkeypatch, choice):
    from types import SimpleNamespace
    calls = []
    response = SimpleNamespace(choices=[] if choice is None else [SimpleNamespace(
        finish_reason='length' if choice == 'length' else 'stop',
        message=SimpleNamespace(content='讲解' if choice == 'valid' else ' '))])
    class FakeClient:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def create(self, **kwargs): calls.append(kwargs); return response
    monkeypatch.setattr(ai, 'OpenAI', FakeClient)
    assert ai.provider({'standard_log': [], 'student_log': []}) == ('讲解' if choice == 'valid' else None)
    assert calls[0]['max_retries'] == 0 and calls[0]['timeout'] == 8
    assert 'password' not in calls[1]['messages'][1]['content']
