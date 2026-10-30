"""S7 cross-stage contracts: real HTTP workflow and the complete legacy upgrade."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.models import LabQuestion
from app.services import exams, operation_explanation
from app.services import s1_migration as s1, s2_migration as s2, s3_migration as s3
from app.services import s4_migration as s4, s5_migration as s5, s6_migration as s6
from app.services.bootstrap import seed_theory
from tests.test_lab_topics import completed
from tests.test_s3_operations import draft, record_standard


def login(client, username, password):
    response = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


def test_fresh_install_admin_authoring_learning_exam_grade_and_restart(client, db_session, monkeypatch):
    import main
    engine = db_session.get_bind()
    monkeypatch.setattr(main, 'engine', engine)
    monkeypatch.setattr(main, 'SessionLocal', sessionmaker(bind=engine))
    time = datetime(2030, 1, 2, 4)
    monkeypatch.setattr(exams, 'now', lambda: time)
    monkeypatch.setattr(operation_explanation.settings, 'deepseek_api_key', '')
    main.on_startup()
    admin = login(client, 'admin', main.DEFAULT_ADMIN_PASSWORD)
    roles = {'admin': admin}
    for role, username, number, classroom in [
        ('teacher', 's7_teacher', None, None),
        ('student', 's7_student', 'S7-001', '信号一班'),
        ('student', 's7_outside', 'S7-002', '信号二班'),
    ]:
        response = client.post('/api/admin/users', headers=admin, json={
            'username': username, 'password': 's7-fixture-password', 'role': role,
            'real_name': username, 'student_id': number, 'class_name': classroom,
        })
        assert response.status_code == 201, response.text
        assert 'password' not in response.text
        roles[username] = login(client, username, 's7-fixture-password')
    teacher, student = roles['s7_teacher'], roles['s7_student']

    # The retained six-topic platform and its history still work in the same installation.
    catalog = client.get('/api/lab-topics/questions', headers=student).json()
    assert len(catalog) == 18 and {q['topic'] for q in catalog} == set(range(1, 7))
    question = db_session.query(LabQuestion).order_by(LabQuestion.id).first()
    theory = client.post(f'/api/lab-topics/questions/{question.key}/submit', headers=student,
                         json={'fingerprint': question.fingerprint, 'answers': completed(question)})
    assert theory.status_code == 201, theory.text

    q = draft(client, teacher)
    q, _ = record_standard(client, teacher, q['id'])
    released = client.post(f"/api/operations/questions/{q['id']}/publish", headers=teacher)
    assert released.status_code == 200, released.text
    q = released.json()
    assert client.get('/api/operations/questions', headers=student).json()['total'] == 1
    assert client.get('/api/operations/questions', headers=roles['s7_outside']).json()['total'] == 0
    response = client.post(f"/api/operation-learning/questions/{q['id']}/begin", headers=student, json={})
    assert response.status_code == 200, response.text
    sid = response.json()['session_id']
    assert 'standard_log' not in response.text
    for sequence, button in enumerate(['D3DA', 'D7DA'], 1):
        response = client.post(f'/api/operation-learning/attempts/{sid}/events', headers=student,
                               json={'event_id': str(uuid4()), 'sequence': sequence, 'action': 'button', 'button_id': button})
        assert response.status_code == 200, response.text
    response = client.post(f'/api/operation-learning/attempts/{sid}/submit', headers=student, json={})
    assert response.status_code == 200, response.text
    assert response.json()['outcome']['score'] == 100
    explanation = client.post(f'/api/operation-learning/attempts/{sid}/explanation', headers=student, json={})
    assert explanation.status_code == 200, explanation.text
    assert explanation.json()['ai_status'] == 'unconfigured'

    response = client.post('/api/exams', headers=teacher, json={
        'name': 'S7完整链路', 'version_id': q['version_id'], 'classes': ['信号一班'],
        'opens_at': exams.iso(time), 'closes_at': exams.iso(time + timedelta(minutes=10)), 'duration_minutes': 5,
    })
    assert response.status_code == 200, response.text
    exam = response.json()
    response = client.post(f"/api/exams/{exam['id']}/publish", headers=teacher, json={'revision': exam['revision']})
    assert response.status_code == 200, response.text
    assert client.post(f"/api/exams/{exam['id']}/begin", headers=roles['s7_outside'], json={'fullscreen': True}).status_code == 404
    assert client.post(f"/api/exams/{exam['id']}/begin", headers=student, json={'fullscreen': False}).status_code == 422
    response = client.post(f"/api/exams/{exam['id']}/begin", headers=student, json={'fullscreen': True})
    assert response.status_code == 200, response.text
    exam_sid = response.json()['session_id']
    for sequence, button in enumerate(['D3DA', 'D7DA'], 1):
        response = client.post(f'/api/exams/attempts/{exam_sid}/events', headers=student,
                               json={'event_id': str(uuid4()), 'sequence': sequence, 'action': 'button', 'button_id': button})
        assert response.status_code == 200, response.text
    base = f'/api/exams/attempts/{exam_sid}'
    response = client.post(base + '/submit', headers=student, json={'expected_sequence': 2})
    assert response.status_code == 200 and response.json()['status'] == 'submitted', response.text
    assert 'score' not in response.text
    response = client.put(base + '/grade', headers=teacher, json={'revision': 0, 'score': '86.50', 'comment': 'S7人工评语'})
    assert response.status_code == 200, response.text
    response = client.post(base + '/grade/confirm', headers=teacher, json={'revision': 1})
    assert response.status_code == 200, response.text
    for path in [base, base + '/log.json', '/api/exams/history']:
        response = client.get(path, headers=student)
        assert response.status_code == 200, response.text
        assert 'score' not in response.text and 'S7人工评语' not in response.text
    response = client.post(base + '/grade/publish', headers=teacher, json={'revision': 2})
    assert response.status_code == 200, response.text
    assert client.get(base, headers=student).json()['grade']['score'] == 86.5
    assert client.get(base, headers=roles['s7_outside']).status_code == 404

    # Dispose the connection pool and run the actual startup path again against saved data.
    db_session.close()
    engine.dispose()
    main.on_startup()
    assert client.get(base, headers=student).json()['grade']['comment'] == 'S7人工评语'
    assert client.get('/api/exams/history', headers=student).json()['total'] == 1
    assert client.get('/api/operation-learning/attempts', headers=student).json()['total'] == 1
    history = client.get('/api/lab-topics/attempts', headers=student, params={'topic': 1})
    assert history.status_code == 200, history.text
    assert history.json()[0]['id'] == theory.json()['id']
    assert client.get(f"/api/operations/questions/{q['id']}", headers=teacher).json()['standard_log'] == q['standard_log']
    assert client.post(f"/api/exams/{exam['id']}/begin", headers=student, json={'fullscreen': True}).json()['session_id'] == exam_sid


def database_rows(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name: db.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall() for name in names}


@pytest.fixture()
def raw_legacy(tmp_path):
    path = tmp_path / 's7-legacy.db'
    with sqlite3.connect(path) as db:
        db.executescript((Path(__file__).parent / 'fixtures/s1_legacy_schema.sql').read_text('utf8'))
        db.execute("INSERT INTO users(id,username,password_hash,role,real_name,student_id,class_name) VALUES(41,'s7-retained','fixture-hash','student','保留学生','S7-OLD','信号一班')")
    engine = create_engine('sqlite:///' + path.as_posix())
    try:
        with Session(engine) as db:
            seed_theory(db)
            original = db.query(LabQuestion).first()
            for key, topic in [('lab-07-01', 7), ('lab-08-01', 8), ('custom-old', 1)]:
                content = copy.deepcopy(original.content)
                content.update(key=key, topic=topic)
                db.add(LabQuestion(key=key, topic=topic, sequence=1, dataset_id=original.dataset_id,
                                   content=content, fingerprint='migration-fixture'))
            db.commit()
        with sqlite3.connect(path) as db:
            for qid, content in db.execute('SELECT id,content FROM lab_questions').fetchall():
                db.execute('INSERT INTO lab_attempts(question_id,student_id,question_snapshot,answers,result,review) VALUES(?,41,?,?,?,?)',
                           (qid, content, '{"retained":"answer"}', '{"status":"reviewed"}', '{"comment":"旧评语"}'))
    finally:
        engine.dispose()
    return path


def upgrade(path):
    s1.migrate_database(path, apply=True)
    s2.migrate_database(path, apply=True)
    for migration in (s3, s4, s5, s6):
        migration.migrate(path, True)


def test_full_legacy_s1_through_s6_repeat_and_restart_preserves_retained_values(raw_legacy, monkeypatch):
    import main
    before = database_rows(raw_legacy)
    upgrade(raw_legacy)
    after = database_rows(raw_legacy)
    assert not set(after).intersection(s1.REMOVED_TABLES)
    assert len(after['lab_questions']) == len(after['lab_attempts']) == 18
    assert [row[:len(before['users'][0])] for row in after['users']] == before['users']
    assert after['lab_questions'] == before['lab_questions'][:18]
    assert [row[:len(before['lab_attempts'][0])] for row in after['lab_attempts']] == before['lab_attempts'][:18]
    assert after['shunting_routes'] == before['shunting_routes']
    assert after['shunting_datasets'] == before['shunting_datasets']
    with sqlite3.connect(raw_legacy) as db:
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        identity = json.loads(db.execute('SELECT identity_snapshot FROM lab_attempts LIMIT 1').fetchone()[0])
        assert identity['source'] == 'migration_current_identity' and identity['id'] == 41
    upgrade(raw_legacy)
    assert database_rows(raw_legacy) == after
    engine = create_engine('sqlite:///' + raw_legacy.as_posix())
    try:
        monkeypatch.setattr(main, 'engine', engine)
        monkeypatch.setattr(main, 'SessionLocal', sessionmaker(bind=engine))
        main.on_startup()
        started = database_rows(raw_legacy)
        main.on_startup()
        assert database_rows(raw_legacy) == started
        assert len(started['users']) == 2  # Original student and newly initialized administrator.
        for table in set(after) - {'users'}:
            assert started[table] == after[table]
        assert s6.TABLES <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_failed_account_upgrade_can_resume_without_repeating_destructive_cleanup(raw_legacy, tmp_path):
    s1.migrate_database(raw_legacy, apply=True)
    before = database_rows(raw_legacy)
    with pytest.raises(RuntimeError, match='injected failure'):
        s2.migrate_database(raw_legacy, apply=True, backup_dir=tmp_path / 'failed-backup', _fail_after_alter=True)
    assert database_rows(raw_legacy) == before
    backup = next((tmp_path / 'failed-backup').glob('*.db'))
    assert database_rows(backup) == before
    upgrade(raw_legacy)
    assert len(database_rows(raw_legacy)['lab_attempts']) == 18
    engine = create_engine('sqlite:///' + raw_legacy.as_posix())
    try:
        for check in (s1.require_current_schema, s2.require_account_schema, s3.require_operation_schema,
                      s4.require_learning_schema, s5.require_exam_schema, s6.require_grade_schema):
            check(engine)
    finally:
        engine.dispose()
