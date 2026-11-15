"""S3 contracts exercise real APIs, SQLite rows and the unchanged station engine."""
import copy
import json
from time import monotonic, time
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.models import User
from app.models.operation import OperationQuestion, OperationVersion, OperationSession, OperationEvent
from app.services import operations as service
from app.services.operation_runtime import pack, unpack
from app.services.simulation_console.reference_runtime import ReferenceSimulationService
from app.services.simulation_console.reference_station import reference_station_package
from tests.helpers import auth_headers

BASE = '/api/operations'


@pytest.fixture()
def actors(client):
    return {role: auth_headers(client, 's3_' + role, role) for role in ['teacher', 'admin', 'student']}


def draft(client, auth, **values):
    body = {'title': '调车进路练习', 'prompt': '办理D3到D7调车进路。', 'classes': ['信号一班'],
            'initial': {'interval_available': True, 'occupied_sections': []}, **values}
    result = client.post(BASE + '/questions', headers=auth, json=body)
    assert result.status_code == 200, result.text
    return result.json()


def start(client, auth, qid, kind='recording'):
    result = client.post(f'{BASE}/questions/{qid}/sessions', headers=auth, json={'kind': kind})
    assert result.status_code == 200, result.text
    return result.json()


def click(client, auth, session, action='button', **values):
    payload = {'event_id': str(uuid4()), 'sequence': session['revision'] + 1, 'action': action, **values}
    result = client.post(f"{BASE}/sessions/{session['session_id']}/events", headers=auth, json=payload)
    assert result.status_code == 200, result.text
    return result.json(), payload


def record_standard(client, auth, qid):
    session = start(client, auth, qid)
    session, _ = click(client, auth, session, button_id='D3DA')
    session, _ = click(client, auth, session, button_id='D7DA')
    sid = session['session_id']
    assert client.post(f'{BASE}/sessions/{sid}/stop', headers=auth).status_code == 200
    saved = client.post(f'{BASE}/sessions/{sid}/save-standard', headers=auth)
    assert saved.status_code == 200, saved.text
    return saved.json(), session


def test_s3_course_sharing_admin_and_student_api_boundaries(client, actors):
    other = auth_headers(client, 's3_other_teacher', 'teacher')
    q = draft(client, actors['teacher'])
    root = f"{BASE}/questions/{q['id']}"
    session = start(client, actors['teacher'], q['id'])
    assert client.get(root, headers=other).status_code == 200
    assert client.get(BASE + '/questions', headers=other).json()['total'] == 1
    assert client.get(root, headers=actors['admin']).status_code == 200
    assert client.get(BASE + '/questions', headers=actors['admin']).json()['total'] == 1
    assert client.post(root + '/publish', headers=other).status_code == 409
    assert client.post(root + '/disable', headers=other).status_code == 200
    assert client.get(f"{BASE}/sessions/{session['session_id']}/log.json", headers=other).status_code == 200
    assert client.get(f"{BASE}/sessions/{session['session_id']}", headers=other).json()['read_only'] is True
    assert client.post(f"{BASE}/sessions/{session['session_id']}/stop", headers=other).status_code == 404
    assert client.get(f"{BASE}/sessions/{session['session_id']}/log.json", headers=actors['admin']).status_code == 200
    assert client.get(f"{BASE}/sessions/{session['session_id']}", headers=actors['admin']).json()['read_only'] is True
    assert client.get(BASE + '/questions', headers=actors['student']).json()['total'] == 0
    assert client.get(root, headers=actors['student']).status_code == 403
    assert client.get(BASE + '/station', headers=actors['student']).status_code == 403
    assert client.post(root + '/sessions', headers=actors['student'], json={'kind':'recording'}).status_code == 403
    assert client.post(BASE + '/questions', headers=actors['student'], json={}).status_code == 403


@pytest.mark.parametrize('changes', [{'title': None}, {'prompt': ' '}, {'classes': []}, {}])
def test_incomplete_or_unrecorded_draft_cannot_publish(client, actors, changes):
    q = draft(client, actors['teacher'], **changes)
    assert client.post(f"{BASE}/questions/{q['id']}/publish", headers=actors['teacher']).status_code == 409


@pytest.mark.parametrize('body', [
    {'initial': {'occupied_sections':['out-of-station']}},
    {'initial': {'unknown_fault':'fake'}}, {'classes':[' ']}, {'classes':['班'*101]},
])
def test_initial_configuration_is_server_validated(client, actors, body):
    result = client.post(BASE + '/questions', headers=actors['teacher'], json=body)
    assert result.status_code == 422


def test_click_retry_real_repeat_rejection_order_and_pin_redaction(client, actors, monkeypatch, db_session):
    monkeypatch.setenv('SIMULATOR_TRAINING_PIN', 'test-operator-secret')
    auth = actors['teacher']
    q = draft(client, auth)
    session = start(client, auth, q['id'])
    session, payload = click(client, auth, session, 'function', button_id='SIGNAL_SEAL')
    sid = session['session_id']
    # Function selection is persisted before any target exists.
    assert session['pending']['type'] == 'SIGNAL_SEAL'
    assert len(session['events']) == 1
    again = client.post(f'{BASE}/sessions/{sid}/events', headers=auth, json=payload)
    assert again.status_code == 200 and again.json()['revision'] == 1
    assert len(again.json()['events']) == 1
    changed = {**payload, 'button_id':'SIGNAL_UNSEAL'}
    assert client.post(f'{BASE}/sessions/{sid}/events', headers=auth, json=changed).status_code == 409
    session, _ = click(client, auth, session, 'target', target_id='1', target_kind='switch')
    assert not session['event']['result']['accepted']
    assert session['pending']['type'] == 'SIGNAL_SEAL'
    session, _ = click(client, auth, session, 'target', target_id='D3', target_kind='signal', pin='wrong-secret')
    assert not session['event']['result']['accepted']
    session, _ = click(client, auth, session, 'function', button_id='SIGNAL_SEAL')
    session, _ = click(client, auth, session, 'target', target_id='D3', target_kind='signal', pin='test-operator-secret')
    assert session['event']['result']['accepted']
    session, _ = click(client, auth, session, button_id='D3DA')
    assert not session['event']['result']['accepted']  # sealed button, still a click
    session, _ = click(client, auth, session, button_id='D3DA')
    assert session['revision'] == 7  # true repeat is a second event
    assert [e['sequence'] for e in session['events']] == list(range(1, 8))
    gap = {'event_id':str(uuid4()), 'sequence':9, 'action':'button', 'button_id':'D7DA'}
    assert client.post(f'{BASE}/sessions/{sid}/events', headers=auth, json=gap).status_code == 409
    exported = client.get(f'{BASE}/sessions/{sid}/log.json', headers=auth)
    assert exported.status_code == 200 and 'attachment' in exported.headers['content-disposition']
    raw = exported.content.decode('utf-8')
    assert '调车' not in raw or json.loads(raw)
    for secret in ['wrong-secret', 'test-operator-secret', 'password123', 'access_token', 'password_hash']:
        assert secret not in raw
        assert secret not in json.dumps(session)
    persisted = json.dumps(db_session.get(OperationSession, sid).engine_state)
    assert 'test-operator-secret' not in persisted
    assert db_session.scalar(select(service.func.count(OperationEvent.id))) == 7


def test_no_management_commands_or_arbitrary_payload_in_standard(client, actors):
    auth = actors['teacher']
    q = draft(client, auth)
    session = start(client, auth, q['id'])
    for command in ['SET_SECTION_OCCUPANCY', 'BLOCK_PEER_ACCEPT', 'SET_SWITCH_INDICATION', 'ADVANCE_TRAIN']:
        body = {'event_id':str(uuid4()), 'sequence':1, 'action':'function', 'button_id':command}
        assert client.post(f"{BASE}/sessions/{session['session_id']}/events", headers=auth, json=body).status_code == 422
    body = {'event_id':str(uuid4()), 'sequence':1, 'action':'button', 'button_id':'D3DA', 'parameters':{'pin':'secret'}}
    assert client.post(f"{BASE}/sessions/{session['session_id']}/events", headers=auth, json=body).status_code == 422


def test_record_preview_start_from_same_initial_and_do_not_create_theory_answers(client, actors, db_session):
    from app.models import LabAttempt
    name = reference_station_package()['sections'][0]['name']
    initial = {'interval_available':False, 'occupied_sections':[name]}
    q = draft(client, actors['teacher'], initial=initial)
    one = start(client, actors['teacher'], q['id'])
    assert one['snapshot']['sections'][name]['occupied']
    assert one['snapshot']['interval_available'] is False
    one, _ = click(client, actors['teacher'], one, 'function', button_id='SWITCH_TOTAL_REVERSE')
    two = start(client, actors['teacher'], q['id'], 'preview')
    assert two['snapshot']['selected_buttons'] == [] and two['pending'] is None
    assert two['events'] == [] and two['snapshot']['sections'][name]['occupied']
    assert client.get(f"{BASE}/sessions/{one['session_id']}", headers=actors['teacher']).json()['status'] == 'abandoned'
    assert db_session.query(LabAttempt).count() == 0
    assert client.post(f"{BASE}/sessions/{two['session_id']}/stop", headers=actors['teacher']).status_code == 200
    assert client.post(f"{BASE}/sessions/{two['session_id']}/save-standard", headers=actors['teacher']).status_code == 409


def test_resume_function_and_route_selection_and_expired_context(client, actors, db_session):
    auth = actors['teacher']
    session = start(client, auth, draft(client, auth)['id'])
    session, _ = click(client, auth, session, button_id='D3DA')
    sid = session['session_id']
    # No process-global engine cache is involved. Every request rehydrates SQLite state.
    restored = client.get(f'{BASE}/sessions/{sid}', headers=auth).json()
    assert restored['snapshot']['selected_buttons'] == ['D3DA']
    session, _ = click(client, auth, restored, 'function', button_id='CANCEL_ROUTE')
    assert client.get(f'{BASE}/sessions/{sid}', headers=auth).json()['pending']['type'] == 'CANCEL_ROUTE'
    row = db_session.get(OperationSession, sid)
    context = copy.deepcopy(row.context)
    context['pending']['expires_at'] = time() - 1
    row.context = context
    state = copy.deepcopy(row.engine_state)
    state['session']['selection_deadline'] = time() - 1
    row.engine_state = state
    db_session.commit()
    restored = client.get(f'{BASE}/sessions/{sid}', headers=auth).json()
    assert restored['pending'] is None
    assert restored['snapshot']['selected_buttons'] == []
    assert restored['revision'] == 2  # automatic timeout never becomes a business click


def test_all_engine_timer_types_survive_restart_without_reset(monkeypatch):
    import app.services.operation_runtime as persistence
    engine = ReferenceSimulationService(reference_station_package())
    sid = engine.new_session(99)['session_id']
    session = engine.sessions[sid]
    clock = monotonic()
    session.selection_deadline = clock + 10
    session.routes['test'] = {'manual_release_due':clock+20, 'signal_open_due':clock+30,
        'guide_deadline':clock+40, 'release_due':{'1G':clock+50},
        'cancel_pending':{'due':clock+60}, 'remaining':{'1G'}}
    engine._state(session)['fault_releases'] = {'1G':clock+70}
    engine._state(session)['point_motions'] = {'1':{'due':clock+80,'deadline':clock+90}}
    encoded = pack(engine, sid)
    assert encoded['session']['selection_deadline'] > time()
    json.dumps(encoded)
    # Simulate new process monotonic origin and five elapsed wall-clock seconds.
    wall = time()
    monkeypatch.setattr(persistence, 'monotonic', lambda:100)
    monkeypatch.setattr(persistence, 'time', lambda:wall+5)
    new_engine, new_session = unpack(reference_station_package(), encoded)
    assert new_session.selection_deadline == pytest.approx(105, abs=.2)
    assert new_session.routes['test']['manual_release_due'] == pytest.approx(115, abs=.2)
    assert new_session.routes['test']['signal_open_due'] == pytest.approx(125, abs=.2)
    assert new_session.routes['test']['guide_deadline'] == pytest.approx(135, abs=.2)
    assert new_session.routes['test']['release_due']['1G'] == pytest.approx(145, abs=.2)
    assert new_session.routes['test']['cancel_pending']['due'] == pytest.approx(155, abs=.2)
    assert new_engine._state(new_session)['fault_releases']['1G'] == pytest.approx(165, abs=.2)
    assert new_engine._state(new_session)['point_motions']['1']['deadline'] == pytest.approx(185, abs=.2)
    assert new_session.routes['test']['remaining'] == {'1G'}


def test_publication_freezes_version_hides_answer_and_new_draft_does_not_replace_old(client, actors, db_session):
    auth = actors['teacher']
    q = draft(client, auth)
    q, session = record_standard(client, auth, q['id'])
    root = f"{BASE}/questions/{q['id']}"
    published = client.post(root + '/publish', headers=auth)
    assert published.status_code == 200, published.text
    frozen = published.json()
    visible = client.get(BASE + '/questions', headers=actors['student']).json()
    assert visible['total'] == 1
    assert visible['items'][0]['number'] == 1
    assert 'standard_log' not in json.dumps(visible) and 'standard_session_id' not in json.dumps(visible)
    other = auth_headers(client, 's3_other_class', 'student')
    student = db_session.query(User).filter_by(username='s3_other_class').one()
    student.class_name = '信号二班'; db_session.commit()
    assert client.get(BASE + '/questions', headers=other).json()['total'] == 0
    update = {'title':'新版本题目', 'prompt':q['prompt'], 'classes':q['classes'],
              'initial':q['initial'], 'revision':frozen['revision']}
    changed = client.put(root, headers=auth, json=update)
    assert changed.status_code == 200 and changed.json()['number'] == 2
    assert changed.json()['standard_log'] is None
    assert client.get(BASE + '/questions', headers=actors['student']).json()['items'][0]['title'] == q['title']
    old = client.get(root + '/versions/1', headers=auth).json()
    assert old['standard_log'] == frozen['standard_log'] and old['title'] == frozen['title']
    record_standard(client, auth, q['id'])
    assert client.post(root + '/publish', headers=auth).status_code == 200
    assert client.get(BASE + '/questions', headers=actors['student']).json()['items'][0]['number'] == 2
    assert client.post(root + '/disable', headers=auth).status_code == 200
    assert client.get(BASE + '/questions', headers=actors['student']).json()['total'] == 0
    assert client.get(root + '/versions/1', headers=auth).json()['standard_log'] == frozen['standard_log']
    assert client.post(root + '/sessions', headers=auth, json={'kind':'preview'}).status_code == 409


def test_stopped_log_is_sealed_and_retry_remains_idempotent(client, actors):
    auth = actors['teacher']; q = draft(client, auth)
    session = start(client, auth, q['id'])
    session, envelope = click(client, auth, session, button_id='D3DA')
    root = f"{BASE}/sessions/{session['session_id']}"
    for _ in range(2):
        assert client.post(root + '/stop', headers=auth).json()['status'] == 'stopped'
    retried = client.post(root + '/events', headers=auth, json=envelope)
    assert retried.status_code == 200 and retried.json()['revision'] == 1
    envelope.update(event_id=str(uuid4()), sequence=2)
    assert client.post(root + '/events', headers=auth, json=envelope).status_code == 409


def test_empty_standard_active_publish_and_initial_change_invalidation(client, actors):
    auth = actors['teacher']; q = draft(client, auth)
    session = start(client, auth, q['id'])
    sid = session['session_id']
    client.post(f'{BASE}/sessions/{sid}/stop', headers=auth)
    assert client.post(f'{BASE}/sessions/{sid}/save-standard', headers=auth).status_code == 409
    q, _ = record_standard(client, auth, q['id'])
    preview = start(client, auth, q['id'], 'preview')
    assert client.post(f"{BASE}/questions/{q['id']}/publish", headers=auth).status_code == 409
    body = {key:q[key] for key in ['title','prompt','classes','initial','revision']}
    assert client.put(f"{BASE}/questions/{q['id']}", headers=auth, json=body).status_code == 409
    client.post(f"{BASE}/sessions/{preview['session_id']}/stop", headers=auth)
    body['initial'] = {'interval_available':False, 'occupied_sections':[]}
    changed = client.put(f"{BASE}/questions/{q['id']}", headers=auth, json=body)
    assert changed.status_code == 200 and changed.json()['standard_log'] is None


def test_route_targets_use_definition_ids_not_random_instance_ids(client, actors):
    auth = actors['teacher']; q = draft(client, auth)
    session = start(client, auth, q['id'])
    session, _ = click(client, auth, session, button_id='D3DA')
    session, _ = click(client, auth, session, button_id='D7DA')
    assert session['snapshot']['routes']
    instance_id = session['snapshot']['routes'][0]['id']
    session, _ = click(client, auth, session, 'function', button_id='CANCEL_ROUTE')
    session, _ = click(client, auth, session, 'target', target_id='D3', target_kind='signal')
    assert session['event']['target_id'].startswith('route:')
    assert instance_id not in json.dumps(session['event'])


def test_six_items_per_page(client, actors):
    for i in range(7):
        draft(client, actors['teacher'], title=f'题目{i}')
    one = client.get(BASE + '/questions', headers=actors['teacher']).json()
    two = client.get(BASE + '/questions?page=2', headers=actors['teacher']).json()
    assert one['total'] == 7 and len(one['items']) == 6 and len(two['items']) == 1


def test_actual_persisted_record_can_be_opened_by_an_independent_engine(client, actors, db_session):
    auth = actors['teacher']; q = draft(client, auth)
    session = start(client, auth, q['id'])
    session, _ = click(client, auth, session, 'function', button_id='SWITCH_TOTAL_REVERSE')
    saved = db_session.get(OperationSession, session['session_id'])
    new_engine, state = unpack(reference_station_package(), json.loads(json.dumps(saved.engine_state)))
    assert new_engine.snapshot(state.id, state.owner_id)['switches'] == session['snapshot']['switches']
    assert saved.context['pending']['type'] == 'SWITCH_TOTAL_REVERSE'


def test_station_version_drift_stops_execution_preserves_download(client, actors, monkeypatch):
    auth = actors['teacher']; q = draft(client, auth)
    session = start(client, auth, q['id'])
    monkeypatch.setattr(service, 'station_version', lambda:'changed-rule-version')
    assert client.get(f"{BASE}/sessions/{session['session_id']}", headers=auth).status_code == 409
    assert client.get(f"{BASE}/sessions/{session['session_id']}/log.json", headers=auth).status_code == 200


def test_separate_database_sessions_cannot_overwrite_newer_click_state(client, actors, db_session):
    from sqlalchemy.orm import Session
    from fastapi import HTTPException
    from app.schemas.operation import Click
    auth = actors['teacher']; q = draft(client, auth)
    session = start(client, auth, q['id'])
    sid = session['session_id']
    with Session(db_session.bind) as first, Session(db_session.bind) as second:
        row1 = first.get(OperationSession, sid)
        row2 = second.get(OperationSession, sid)
        owner1, owner2 = first.get(User, row1.owner_id), second.get(User, row2.owner_id)
        service.click(first, owner1, sid, Click(event_id=uuid4(), sequence=1, action='button', button_id='D3DA'))
        with pytest.raises(HTTPException) as caught:
            service.click(second, owner2, sid, Click(event_id=uuid4(), sequence=1, action='button', button_id='D7DA'))
        assert caught.value.status_code == 409
    restored = client.get(f'{BASE}/sessions/{sid}', headers=auth).json()
    assert restored['revision'] == 1 and restored['snapshot']['selected_buttons'] == ['D3DA']


def test_question_log_and_pending_context_survive_a_real_new_process(client, actors, db_session):
    import os
    from pathlib import Path
    import subprocess
    import sys
    auth = actors['teacher']; q = draft(client, auth)
    q, _ = record_standard(client, auth, q['id'])
    session = start(client, auth, q['id'], 'preview')
    session, _ = click(client, auth, session, 'function', button_id='SWITCH_TOTAL_NORMAL')
    environment = {**os.environ, 'DATABASE_URL':str(db_session.bind.url), 'DEEPSEEK_API_KEY':''}
    code = '''import json, sys
from app.core.database import SessionLocal
from app.models.operation import OperationQuestion, OperationVersion, OperationSession
from app.services.operation_runtime import unpack
from app.services.simulation_console.reference_station import reference_station_package
with SessionLocal() as db:
    q=db.get(OperationQuestion, int(sys.argv[1]))
    s=db.get(OperationSession, sys.argv[2])
    v=db.get(OperationVersion, s.version_id)
    engine,state=unpack(reference_station_package(), s.engine_state)
    print(json.dumps({'question_id':q.id, 'log_count':len(v.standard_log), 'pending':s.context['pending']['type'], 'session_id':state.id}))
'''
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c', code, str(q['id']), session['session_id']],
        cwd=backend, env=environment, capture_output=True, text=True, check=True, timeout=20)
    restored = json.loads(result.stdout)
    assert restored == {'question_id':q['id'], 'log_count':2, 'pending':'SWITCH_TOTAL_NORMAL', 'session_id':session['session_id']}
