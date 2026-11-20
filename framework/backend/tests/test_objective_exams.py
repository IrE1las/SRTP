"""Objective exams exercise real HTTP permissions, freezing, persistence and grading."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
import json
from uuid import uuid4

import pytest
from pathlib import Path
import sqlite3
from sqlalchemy import select, inspect, event
from sqlalchemy.orm import sessionmaker

from app.models import User
from app.models.chapter_bank import ChapterBankQuestion
from app.models.exam import Exam, ExamAttempt, ExamParticipant, ObjectiveExamResponse
from app.models.operation import OperationSession
from app.services import exams, chapter_bank, chapter_practice
from app.services.objective_exam_upgrade import upgrade
from tests.helpers import auth_headers
from tests.test_s5_exams import course, clock, publish as publish_operation, begin as begin_operation

ROOT = '/api/exams'


@pytest.fixture()
def objective_course(client, db_session, monkeypatch):
    clock = [datetime(2030, 1, 2, 4)]
    monkeypatch.setattr(exams, 'now', lambda: clock[0])
    roles = {role: auth_headers(client, 'objective_' + role, role) for role in ['teacher', 'student']}
    chapter_bank.import_bank(db_session, chapter_bank.load_bank())
    db_session.commit()
    questions = []
    for values in [
        {'kind': 'choice', 'answer': 'B', 'options': ['甲', '乙']},
        {'kind': 'multi', 'answer': ['A', 'C'], 'options': ['甲', '乙', '丙']},
        {'kind': 'true_false', 'answer': False, 'options': []},
        {'kind': 'cell', 'answer': ['锁闭', '2'], 'accepted': [['锁 闭'], ['二']], 'options': []},
    ]:
        result = client.post('/api/chapter-bank/manage/questions', headers=roles['teacher'], json={
            'chapter': 1, 'stem': '教师考试题：' + values['kind'], 'source_reference': '教师已核对',
            'explanation': '本题的核验解析', **values})
        assert result.status_code == 201, result.text
        questions.append(result.json())
    body = {'name': '客观题考试', 'kind': 'objective', 'classes': ['信号一班'],
            'objective_questions': [{'question_id': q['id'], 'points': 25} for q in questions],
            'opens_at': exams.iso(clock[0]), 'closes_at': exams.iso(clock[0] + timedelta(minutes=10)),
            'duration_minutes': 5}
    return roles, questions, body, clock


def publish(client, course, **changes):
    roles, _, body, _ = course
    response = client.post(ROOT, headers=roles['teacher'], json={**body, **changes})
    assert response.status_code == 200, response.text
    draft = response.json()
    response = client.post(f"{ROOT}/{draft['id']}/publish", headers=roles['teacher'], json={'revision': draft['revision']})
    assert response.status_code == 200, response.text
    return response.json()


def begin(client, course, exam):
    response = client.post(f"{ROOT}/{exam['id']}/begin", headers=course[0]['student'], json={'fullscreen': True})
    assert response.status_code == 200, response.text
    return response.json()


def save(client, course, attempt, answers, revision=0):
    return client.put(f"{ROOT}/attempts/{attempt['session_id']}/answers", headers=course[0]['student'],
                      json={'revision': revision, 'answers': answers})


def submit(client, course, attempt, revision=0):
    response = client.post(f"{ROOT}/attempts/{attempt['session_id']}/submit", headers=course[0]['student'],
                           json={'expected_sequence': revision})
    assert response.status_code == 200, response.text
    return response.json()


def correct_answers(course):
    q = course[1]
    return {q[0]['id']: 'B', q[1]['id']: ['C', 'A'], q[2]['id']: False, q[3]['id']: ['锁 闭', '二']}


def test_catalogue_has_same_182_reviewed_questions_plus_explicit_teacher_questions(client, objective_course, db_session):
    roles, questions, _, _ = objective_course
    result = client.get(ROOT + '/objective-questions', headers=roles['teacher'])
    assert result.status_code == 200 and result.json()['total'] == 186
    assert not any(key in result.text for key in ['correct_answer', 'answer_status', 'accepted', '_practice_rule', '核验解析'])
    assert client.get(ROOT + '/objective-questions', headers=roles['student']).status_code == 403
    filtered = client.get(ROOT + '/objective-questions?kind=multi&search=教师考试题', headers=roles['teacher']).json()
    assert filtered['total'] == 1 and filtered['items'][0]['id'] == questions[1]['id']
    eligible = {row.id for row, _ in chapter_practice.available_questions(db_session)}
    excluded = next(row.id for row in db_session.query(ChapterBankQuestion) if row.id not in eligible)
    assert client.post(ROOT, headers=roles['teacher'], json={**objective_course[2], 'objective_questions': [
        {'question_id': excluded, 'points': 100}]}).status_code == 422


def test_publish_freezes_order_points_questions_rules_and_roster_without_simulator(client, objective_course, db_session):
    exam = publish(client, objective_course)
    roles, questions, _, _ = objective_course
    row = db_session.get(ChapterBankQuestion, questions[0]['id'])
    row.content = {**deepcopy(row.content), 'stem': '未来题干', 'answer': 'A', '_deleted': True}
    student = db_session.scalar(select(User).where(User.username == 'objective_student'))
    student.class_name = '转入班'
    db_session.commit()
    attempt = begin(client, objective_course, exam)
    assert attempt['kind'] == 'objective' and attempt['identity']['class_name'] == '信号一班'
    assert [q['id'] for q in attempt['question']['items']] == [q['id'] for q in questions]
    assert attempt['question']['items'][0]['stem'] == '教师考试题：choice'
    assert db_session.query(OperationSession).count() == 0
    assert begin(client, objective_course, exam)['session_id'] == attempt['session_id']
    assert save(client, objective_course, attempt, correct_answers(objective_course)).status_code == 200
    submit(client, objective_course, attempt, 1)
    teacher = client.get(f"{ROOT}/attempts/{attempt['session_id']}", headers=roles['teacher']).json()
    assert teacher['objective_evaluation']['score'] == 100


@pytest.mark.parametrize('questions', [[], [{'question_id': 'missing', 'points': 100}],
                                     [{'question_id': 'duplicate', 'points': 50}] * 2])
def test_invalid_or_empty_selection_never_publishes(client, objective_course, questions):
    roles, _, body, _ = objective_course
    result = client.post(ROOT, headers=roles['teacher'], json={**body, 'objective_questions': questions})
    if result.status_code == 200:
        assert client.post(f"{ROOT}/{result.json()['id']}/publish", headers=roles['teacher'], json={'revision': 1}).status_code == 422
    else:
        assert result.status_code == 422


def test_draft_validation_revision_copy_withdraw_and_source_becoming_unavailable(client, objective_course, db_session):
    roles, qs, body, _ = objective_course
    bad = client.post(ROOT, headers=roles['teacher'], json={**body, 'objective_questions': [{'question_id': qs[0]['id'], 'points': 99}]}).json()
    assert client.post(f"{ROOT}/{bad['id']}/publish", headers=roles['teacher'], json={'revision': 1}).status_code == 422
    edited = client.put(f"{ROOT}/{bad['id']}", headers=roles['teacher'], json={**body, 'revision': 1})
    assert edited.status_code == 200
    assert client.put(f"{ROOT}/{bad['id']}", headers=roles['teacher'], json={**body, 'revision': 1}).status_code == 409
    exam = publish(client, objective_course)
    copied = client.post(f"{ROOT}/{exam['id']}/copy", headers=roles['teacher']).json()
    assert copied['kind'] == 'objective' and copied['objective_questions'] == body['objective_questions']
    assert copied['participant_count'] == 0 and copied['status'] == 'draft'
    withdrawn = client.post(f"{ROOT}/{exam['id']}/withdraw", headers=roles['teacher'], json={'revision': exam['revision']}).json()
    assert withdrawn['kind'] == 'objective' and withdrawn['question'] is None and withdrawn['participant_count'] == 0
    row = db_session.get(ChapterBankQuestion, qs[0]['id']); row.content = {**row.content, '_deleted': True}; db_session.commit()
    assert client.post(f"{ROOT}/{copied['id']}/publish", headers=roles['teacher'], json={'revision': copied['revision']}).status_code == 422
    config = client.get(f"{ROOT}/{copied['id']}", headers=roles['teacher']).json()
    assert config['objective_items'][0]['unavailable'] is True


def test_autosave_partial_answers_revision_conflict_retry_and_exact_submit(client, objective_course, db_session):
    attempt = begin(client, objective_course, publish(client, objective_course))
    qs = objective_course[1]
    partial = {qs[1]['id']: [], qs[2]['id']: False, qs[3]['id']: ['锁闭', '']}
    first = save(client, objective_course, attempt, partial)
    assert first.status_code == 200 and first.json()['answer_revision'] == 1
    assert save(client, objective_course, attempt, partial).json()['answer_revision'] == 1
    assert save(client, objective_course, attempt, correct_answers(objective_course)).status_code == 409
    response = client.get(f"{ROOT}/attempts/{attempt['session_id']}", headers=objective_course[0]['student']).json()
    assert response['answers'] == partial
    assert client.post(f"{ROOT}/attempts/{attempt['session_id']}/submit", headers=objective_course[0]['student'], json={'expected_sequence': 0}).status_code == 409
    final = submit(client, objective_course, attempt, 1)
    assert final['status'] == 'submitted' and 'objective_evaluation' not in final
    assert db_session.get(ObjectiveExamResponse, attempt['session_id']).evaluation['score'] == 25
    assert db_session.get(ObjectiveExamResponse, attempt['session_id']).evaluation['items'][3]['blank_results'] == [True, False]
    assert submit(client, objective_course, attempt, 1)['submitted_at'] == final['submitted_at']
    assert save(client, objective_course, attempt, correct_answers(objective_course), 1).status_code == 409


@pytest.mark.parametrize('index,answer', [(0, 'Z'), (1, ['A', 'A']), (1, {'a': True}), (2, 'false'), (2, 0), (3, ['锁闭']), (3, [2, '二'])])
def test_malformed_answers_rejected_without_changing_draft(client, objective_course, index, answer):
    attempt = begin(client, objective_course, publish(client, objective_course))
    assert save(client, objective_course, attempt, {objective_course[1][index]['id']: answer}).status_code == 422
    assert client.get(f"{ROOT}/attempts/{attempt['session_id']}", headers=objective_course[0]['student']).json()['answers'] == {}


def test_teacher_and_student_scoping_and_no_answer_feedback_until_released_and_closed(client, objective_course):
    roles, _, _, clock = objective_course
    other = auth_headers(client, 'objective_other_teacher', 'teacher')
    peer = auth_headers(client, 'objective_peer', 'student')
    exam = publish(client, objective_course)
    attempt = begin(client, objective_course, exam)
    sid = attempt['session_id']
    for auth in [other, peer]:
        for path in [f'{ROOT}/attempts/{sid}', f'{ROOT}/attempts/{sid}/log.json']:
            assert client.get(path, headers=auth).status_code == 404
    assert client.put(f'{ROOT}/attempts/{sid}/answers', headers=peer, json={'revision': 0, 'answers': {}}).status_code == 404
    assert client.put(f'{ROOT}/attempts/{sid}/answers', headers=roles['teacher'], json={'revision': 0, 'answers': {}}).status_code == 403
    save(client, objective_course, attempt, correct_answers(objective_course))
    submit(client, objective_course, attempt, 1)
    for path in [f'{ROOT}/attempts/{sid}', f'{ROOT}/attempts/{sid}/log.json']:
        text = client.get(path, headers=roles['student']).text
        assert not any(key in text for key in ['correct_answer', 'correct', 'explanation', '_practice_rule', 'objective_evaluation'])
    assert client.post(f'{ROOT}/attempts/{sid}/grade/publish', headers=other, json={'revision': 0, 'score': 100}).status_code == 404
    assert client.post(f'{ROOT}/attempts/{sid}/grade/publish', headers=roles['teacher'], json={'revision': 0, 'score': 100}).status_code == 200
    early = client.get(f'{ROOT}/attempts/{sid}', headers=roles['student']).json()
    assert early['grade']['score'] == 100 and 'objective_evaluation' not in early
    clock[0] += timedelta(minutes=10)
    final = client.get(f'{ROOT}/attempts/{sid}', headers=roles['student']).json()
    assert final['objective_evaluation']['score'] == 100
    assert all(item['correct'] for item in final['objective_evaluation']['items'])
    assert client.get(ROOT + '/reviews', headers=roles['teacher']).json()['counts']['published'] == 1
    assert client.get(ROOT + '/reviews', headers=other).json()['total'] == 0


def test_fullscreen_sync_timeout_deadline_restart_and_late_save_seal_saved_answers(client, objective_course, db_session):
    roles, _, _, clock = objective_course
    exam = publish(client, objective_course)
    attempt = begin(client, objective_course, exam)
    sid = attempt['session_id']
    save(client, objective_course, attempt, correct_answers(objective_course))
    sync = client.post(f'{ROOT}/attempts/{sid}/sync', headers=roles['student'], json={'fullscreen': True, 'after_sequence': 0})
    assert sync.status_code == 200 and sync.json()['answers'] == correct_answers(objective_course)
    event = {'event_id': str(uuid4()), 'kind': 'exit', 'occurred_at': exams.iso(clock[0])}
    assert client.post(f'{ROOT}/attempts/{sid}/sync', headers=roles['student'], json={'fullscreen': False, 'events': [event]}).json()['exit_count'] == 1
    assert save(client, objective_course, attempt, {}, 1).status_code == 409
    clock[0] += timedelta(seconds=60)
    factory = sessionmaker(bind=db_session.get_bind())
    with factory() as db:
        exams.settle_all(db)
    db_session.expire_all()
    row = db_session.get(ExamAttempt, sid)
    assert row.finish_reason == 'fullscreen_timeout'
    assert db_session.get(ObjectiveExamResponse, sid).evaluation['score'] == 100
    second = begin(client, objective_course, publish(client, objective_course))
    clock[0] += timedelta(minutes=5)
    assert save(client, objective_course, second, correct_answers(objective_course)).status_code == 409
    assert db_session.get(ExamAttempt, second['session_id']).finish_reason == 'deadline'
    assert db_session.get(ObjectiveExamResponse, second['session_id']).evaluation['score'] == 0


def test_concurrent_begin_and_answer_writes_keep_one_attempt_and_one_revision(client, objective_course, db_session):
    exam = publish(client, objective_course)
    uid = db_session.scalar(select(User.id).where(User.username == 'objective_student'))
    factory = sessionmaker(bind=db_session.get_bind())
    def start():
        with factory() as db, exams.atomic(db):
            return exams.begin(db, db.get(User, uid), exam['id'], True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = list(pool.map(lambda _: start(), range(2)))
    assert attempts[0]['session_id'] == attempts[1]['session_id']
    from app.services.objective_exams import save as persist
    from app.schemas.exam import ObjectiveAnswers
    def write():
        with factory() as db, exams.atomic(db):
            return persist(db, db.get(User, uid), attempts[0]['session_id'], ObjectiveAnswers(revision=0, answers=correct_answers(objective_course)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert [result['answer_revision'] for result in results] == [1, 1]


def test_upgrade_preserves_legacy_attempts_and_child_grades_with_foreign_keys(client, db_session, course):
    engine = db_session.get_bind()
    operation = publish_operation(client, course)
    attempt = begin_operation(client, course[0], operation)
    sid = attempt['session_id']
    assert client.post(f'{ROOT}/attempts/{sid}/submit', headers=course[0]['student'], json={'expected_sequence': 0}).status_code == 200
    assert client.post(f'{ROOT}/attempts/{sid}/grade/publish', headers=course[0]['teacher'], json={'revision': 0, 'score': 83, 'comment': '原操作题成绩'}).status_code == 200
    with engine.connect() as conn:
        before = {table: conn.exec_driver_sql('SELECT * FROM "' + table + '"').all() for table in inspect(engine).get_table_names()}
        values = tuple(conn.exec_driver_sql('SELECT * FROM exam_attempts').one())
    # Restore the old FK definition with actual submitted operation data and grades.
    with engine.begin() as conn:
        conn.exec_driver_sql('DROP TABLE exam_attempts')
        conn.exec_driver_sql('''CREATE TABLE exam_attempts (
            session_id VARCHAR(36) PRIMARY KEY REFERENCES operation_sessions(id), exam_id INTEGER NOT NULL REFERENCES exams(id),
            student_id INTEGER NOT NULL REFERENCES users(id), started_at DATETIME NOT NULL, deadline DATETIME NOT NULL,
            submitted_at DATETIME, finish_reason VARCHAR(40), exit_count INTEGER NOT NULL, fullscreen_state VARCHAR(20) NOT NULL,
            exited_at DATETIME, last_control_at DATETIME, revision INTEGER NOT NULL, UNIQUE(exam_id, student_id))''')
        conn.exec_driver_sql('INSERT INTO exam_attempts VALUES (' + ','.join('?' for _ in values) + ')', values)
    @event.listens_for(engine, 'connect')
    def enforce_foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
    db_session.commit()
    engine.dispose()  # All subsequent connections enforce foreign keys.
    result = upgrade(engine)
    try:
        assert result['changed'] and result['backup']
        with closing(sqlite3.connect(result['backup'])) as backup:
            assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert backup.execute('SELECT score_cents FROM exam_grade_publications').fetchone()[0] == 8300
        assert not any(fk['referred_table'] == 'operation_sessions' for fk in inspect(engine).get_foreign_keys('exam_attempts'))
        with engine.connect() as conn:
            after = {table: conn.exec_driver_sql('SELECT * FROM "' + table + '"').all() for table in before}
            assert conn.exec_driver_sql('PRAGMA foreign_keys').scalar() == 1
            assert conn.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert before == after
        assert upgrade(engine) == {'changed': False}
        assert client.get(f'{ROOT}/attempts/{sid}', headers=course[0]['student']).json()['grade']['score'] == 83
    finally:
        Path(result['backup']).unlink(missing_ok=True)
