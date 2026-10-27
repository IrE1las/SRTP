"""Scope, permission and restoration contracts for S1."""
import copy
from pathlib import Path
import json
import pytest
from sqlalchemy import inspect
from app.models import LabQuestion, LabAttempt, User
from app.services.lab_topics import RETAINED_KEYS, TOPIC_TITLES, ROOT, digest, evaluate
from app.services.bootstrap import seed_theory
from app.services.s1_migration import REMOVED_TABLES
from tests.helpers import auth_headers, _import_payload
from tests.test_lab_topics import completed

@pytest.fixture()
def topics(db_session):
    seed_theory(db_session)
    return db_session.query(LabQuestion).order_by(LabQuestion.key).all()

@pytest.mark.parametrize('role', ['student','teacher','admin'])
@pytest.mark.parametrize('path', [
    '/api/exercises', '/api/exercises/teacher', '/api/exercise-runtime/sessions/1',
    '/api/statistics/student', '/api/statistics/teacher', '/api/ai-scores/1',
    '/api/exam/submit', '/api/exam/shunting/questions', '/api/exam/shunting/dataset',
    '/api/interlocking/stations', '/api/modules/one/experiment-1/questions',
    '/api/simulation-console/station', '/api/simulation-console/sessions',
    '/api/management/questions', '/api/management/reviews',
])
def test_removed_apis_are_unavailable_for_all_roles(client, role, path):
    auth = auth_headers(client, f'scope_{role}', role)
    assert client.get(path, headers=auth).status_code == 404
    assert client.post(path, headers=auth, json={}).status_code == 404

def test_startup_metadata_and_bootstrap_do_not_recreate_removed_features(db_session):
    seed_theory(db_session)
    first = [(q.id,q.fingerprint) for q in db_session.query(LabQuestion).order_by(LabQuestion.id)]
    seed_theory(db_session)
    assert first == [(q.id,q.fingerprint) for q in db_session.query(LabQuestion).order_by(LabQuestion.id)]
    assert len(first) == 18
    assert not set(inspect(db_session.bind).get_table_names()).intersection(REMOVED_TABLES)

def test_only_canonical_six_questions_are_accessible_even_before_migration(client, topics, db_session):
    auth = auth_headers(client, 'scope_reader', 'student')
    for key,topic in [('lab-07-01',7), ('lab-08-01',8), ('custom-legacy',1)]:
        q = copy.deepcopy(topics[0].content)
        q.update(key=key,topic=topic)
        db_session.add(LabQuestion(key=key, topic=topic, sequence=1, dataset_id=topics[0].dataset_id,
                                  content=q, fingerprint=digest(q)))
    db_session.commit()
    response = client.get('/api/lab-topics/questions', headers=auth)
    assert [q['key'] for q in response.json()] == list(RETAINED_KEYS)
    assert [q['topic_info']['title'] for q in response.json()[::3]] == list(TOPIC_TITLES)
    for key in ['lab-07-01','lab-08-01','custom-legacy']:
        base = '/api/lab-topics/questions/' + key
        assert client.get(base, headers=auth).status_code == 404
        assert client.post(base + '/submit', headers=auth,
                           json={'fingerprint':'0'*64,'answers':{}}).status_code == 404
    teacher = auth_headers(client, 'scope_reviewer', 'teacher')
    assert client.get('/api/lab-topics/questions/lab-07-01/rubric', headers=teacher).status_code == 404

@pytest.mark.parametrize('role', ['teacher','admin'])
def test_reviews_and_student_history_are_scoped_to_one_theory_topic(client, topics, db_session, role):
    student = auth_headers(client, 'scoped_student', 'student')
    reviewer = auth_headers(client, 'scoped_reviewer', role)
    for topic in [1,2]:
        q = next(q for q in topics if q.topic == topic)
        assert client.post(f'/api/lab-topics/questions/{q.key}/submit', headers=student,
                           json={'fingerprint':q.fingerprint,'answers':completed(q)}).status_code == 201
    for topic in [1,2]:
        own = client.get('/api/lab-topics/attempts', params={'topic':topic}, headers=student)
        reviews = client.get('/api/lab-topics/reviews', params={'topic':topic}, headers=reviewer)
        assert len(own.json()) == len(reviews.json()) == 1
        assert all(a['topic']==topic for a in own.json()+reviews.json())
    for topic in [7,8,9]:
        assert client.get('/api/lab-topics/attempts',params={'topic':topic},headers=student).status_code == 422
        assert client.get('/api/lab-topics/reviews',params={'topic':topic},headers=reviewer).status_code == 422

def test_admin_summary_has_no_deleted_statistics_and_linked_user_cannot_be_deleted(client, topics, db_session):
    student = auth_headers(client, 'linked_student', 'student')
    admin = auth_headers(client, 's1_admin', 'admin')
    q = topics[0]
    client.post(f'/api/lab-topics/questions/{q.key}/submit', headers=student,
                json={'fingerprint':q.fingerprint,'answers':completed(q)})
    result = client.get('/api/admin/overview',headers=admin)
    assert set(result.json()) == {'user_count','theory_question_count','theory_attempt_count'}
    user = db_session.query(User).filter_by(username='linked_student').one()
    assert client.delete(f'/api/admin/users/{user.id}', headers=admin).status_code == 409
    assert db_session.get(User,user.id) is not None

def test_ai_settings_retains_unrelated_local_configuration(tmp_path, monkeypatch):
    from app.api import settings as api
    env = tmp_path / '.env'
    env.write_text("# local config\nDEEPSEEK_API_KEY='example-only'\nSECRET_KEY='local-test-secret'\n", 'utf8')
    monkeypatch.setattr(api, 'ENV_FILE', env)
    before = api._read_env()
    api._write_env({**before,'DEEPSEEK_MODEL':'test-model'})
    assert api._read_env()['SECRET_KEY'] == 'local-test-secret'
    assert api._read_env()['DEEPSEEK_API_KEY'] == 'example-only'


def test_six_topic_sources_answers_and_standard_station_data_match_the_pre_refactor_contract():
    import hashlib
    contract = json.loads((Path(__file__).parent/'fixtures/s1_retained_contract.json').read_text('utf8'))
    for path,expected in contract['sources'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected, path
    blueprint = json.loads((ROOT/'ai_design/station/report_topic_blueprint.json').read_text('utf8'))
    assert digest(blueprint['topics']) == contract['topics']
    assert {q['key']:digest(q) for q in blueprint['questions']} == contract['questions']
    refs = json.loads((ROOT/'ai_design/station/report_answer_references.json').read_text('utf8'))
    assert {e['question']+'/'+e['field']:digest(e) for e in refs['entries']} == contract['references']
