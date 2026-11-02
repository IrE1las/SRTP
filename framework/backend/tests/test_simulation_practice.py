"""Free practice uses the retained station without sharing assessed sessions."""
import pytest
from sqlalchemy import func, select
from app.api import simulation_practice, theory_console
from app.core.database import Base
from app.services.bootstrap import seed_theory
from tests.helpers import auth_headers

ROOT = '/api/simulation-practice'
THEORY = '/api/lab-topics/questions/lab-01-01/console'


@pytest.fixture()
def student(client, monkeypatch):
    monkeypatch.setattr(simulation_practice, 'store', theory_console.TheoryConsoleStore('自由练习操作台'))
    monkeypatch.setattr(theory_console, 'store', theory_console.TheoryConsoleStore())
    return auth_headers(client, 'free_practice_student', 'student')


def create(client, auth, root=ROOT, **preset):
    response = client.post(root + '/sessions', headers=auth, json=preset)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('role', [None, 'teacher', 'admin'])
def test_all_practice_endpoints_require_a_student(client, role):
    headers = auth_headers(client, 'practice_' + role, role) if role else {}
    endpoints = [
        ('get', '/station', None), ('post', '/sessions', {}),
        ('get', '/sessions/unknown', None), ('get', '/sessions/unknown/replay', None),
        ('post', '/sessions/unknown/buttons', {'button': 'D3DA', 'version': 0}),
        ('post', '/sessions/unknown/clear-selection', {'version': 0}),
        ('post', '/sessions/unknown/advance', {'route_instance_id': 'unknown', 'version': 0}),
        ('post', '/sessions/unknown/commands', {'type': 'SWITCH_SINGLE_LOCK', 'target': '5', 'version': 0}),
    ]
    for method, path, body in endpoints:
        options = {'headers': headers}
        if body is not None:
            options['json'] = body
        assert client.request(method, ROOT + path, **options).status_code == (403 if role else 401)


def test_station_loads_without_questions_and_matches_topics_one_to_four(client, student, db_session):
    from app.models import LabQuestion
    assert db_session.query(LabQuestion).count() == 0
    practice = client.get(ROOT + '/station', headers=student)
    assert practice.status_code == 200
    assert practice.json()['profile'] == 'reference'
    assert practice.json()['counts']['sections'] == 35
    assert 'routes' not in practice.json() and 'source' not in practice.json()
    seed_theory(db_session)
    theory = client.get(THEORY + '/station', headers=student)
    assert practice.json() == theory.json()
    assert create(client, student)['profile'] == 'reference'


def test_students_and_theory_have_separate_state_and_reset_boundaries(client, student, db_session):
    seed_theory(db_session)
    other = auth_headers(client, 'free_practice_other', 'student')
    practice = create(client, student)
    peer = create(client, other)
    theory = create(client, student, THEORY)
    path = ROOT + '/sessions/' + practice['session_id']
    occupied = client.post(path + '/commands', headers=student, json={
        'type': 'SET_SECTION_OCCUPANCY', 'target': '5G', 'payload': {'kind': 'fault'},
        'version': practice['version'],
    })
    assert occupied.status_code == 200 and occupied.json()['accepted']
    assert occupied.json()['snapshot']['sections']['5G']['occupied']
    for root, snapshot, auth in [(ROOT, peer, other), (THEORY, theory, student)]:
        result = client.get(root + '/sessions/' + snapshot['session_id'], headers=auth)
        assert result.status_code == 200 and not result.json()['sections']['5G']['occupied']
    for root, sid, auth in [(ROOT, practice['session_id'], other),
                            (ROOT, theory['session_id'], student),
                            (THEORY, practice['session_id'], student)]:
        invalid = root + '/sessions/' + sid
        assert client.get(invalid, headers=auth).status_code == 409
        assert client.get(invalid + '/replay', headers=auth).status_code == 409
        assert client.post(invalid + '/buttons', headers=auth,
                           json={'button': 'D3DA', 'version': 0}).status_code == 409
    # Reloading reads the existing state; only an explicit reset invalidates it.
    assert client.get(path, headers=student).json()['sections']['5G']['occupied']
    reset = create(client, student)
    assert reset['session_id'] != practice['session_id']
    assert not reset['sections']['5G']['occupied']
    assert client.get(path, headers=student).status_code == 409
    assert client.get(ROOT + '/sessions/' + peer['session_id'], headers=other).status_code == 200
    assert client.get(THEORY + '/sessions/' + theory['session_id'], headers=student).status_code == 200


def test_commands_replay_and_conflicts_never_write_business_records(client, student, db_session):
    def counts():
        return {table.name: db_session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables}
    before = counts()
    snap = create(client, student)
    path = ROOT + '/sessions/' + snap['session_id']
    for kind, target, extra in [
        ('SWITCH_SINGLE_LOCK', '5', {}), ('SWITCH_SINGLE_UNLOCK', '5', {}),
        ('SET_SECTION_OCCUPANCY', '5G', {'payload': {'kind': 'fault'}}),
        ('CLEAR_SECTION_OCCUPANCY', '5G', {}),
    ]:
        response = client.post(path + '/commands', headers=student,
                               json={'type': kind, 'target': target, 'version': snap['version'], **extra})
        assert response.status_code == 200 and response.json()['accepted']
        snap = response.json()['snapshot']
    rejected = client.post(path + '/commands', headers=student, json={
        'type': 'SIGNAL_LIGHT_OFF', 'target': 'D3', 'pin': 'practice-secret-test', 'version': snap['version'],
    })
    assert rejected.status_code == 200 and rejected.json()['reason_code'] == 'INVALID_PIN'
    replay = client.get(path + '/replay', headers=student)
    assert replay.status_code == 200 and len(replay.json()) > 1
    assert 'practice-secret-test' not in replay.text
    assert client.post(path + '/buttons', headers=student, json={'button': 'D3DA', 'version': 0}).status_code == 409
    assert client.post(path + '/commands', headers=student, json={
        'type': 'UNSUPPORTED', 'target': '5', 'version': 0,
    }).status_code == 422
    assert client.post(ROOT + '/sessions', headers=student, json={'question_id': 1}).status_code == 422
    assert client.post(ROOT + '/sessions', headers=student, json={'occupied_sections': ['unknown']}).status_code == 409
    assert counts() == before


def test_route_buttons_clear_selection_and_simulated_train_work(client, student, monkeypatch):
    from app.services.simulation_console import runtime, reference_runtime, console_commands
    clock = [1000.]
    for module in (runtime, reference_runtime, console_commands):
        monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    snap = create(client, student)
    path = ROOT + '/sessions/' + snap['session_id']
    def post(action, **body):
        nonlocal snap
        response = client.post(path + '/' + action, headers=student, json={'version': snap['version'], **body})
        assert response.status_code == 200 and response.json()['accepted'], response.text
        snap = response.json()['snapshot']
    post('buttons', button='D3DA')
    assert snap['selected_buttons'] == ['D3DA']
    post('clear-selection')
    assert snap['selected_buttons'] == []
    for button in ['D3DA', 'D7DA']:
        post('buttons', button=button)
    clock[0] += 2.1
    client.get(path, headers=student)
    clock[0] += .7
    snap = client.get(path, headers=student).json()
    assert snap['signals']['D3']['aspect'] == 'B'
    progress = snap['routes'][0]['progress']
    post('advance', route_instance_id=snap['routes'][0]['id'])
    assert snap['routes'][0]['progress'] == progress + 1


def test_service_restart_allows_a_fresh_session(client, student, monkeypatch):
    old = create(client, student)
    monkeypatch.setattr(simulation_practice, 'store', theory_console.TheoryConsoleStore('自由练习操作台'))
    assert client.get(ROOT + '/sessions/' + old['session_id'], headers=student).status_code == 409
    fresh = create(client, student, interval_available=False)
    assert fresh['session_id'] != old['session_id']
    assert fresh['interval_available'] is False
