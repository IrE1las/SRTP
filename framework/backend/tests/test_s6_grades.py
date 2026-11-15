"""S6 release boundary, permissions, revision concurrency and durable manual grades."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.models import User
from app.models.exam import ExamAttempt
from app.models.exam_grade import ExamGrade, ExamGradePublication, ExamGradeAudit
from app.schemas.exam_grade import GradeDraft
from app.services import exams, exam_grades
from tests.helpers import auth_headers
from tests.test_s5_exams import ROOT, clock, course, publish, begin, control, sync, event


@pytest.fixture()
def submitted(client, course):
    roles = course[0]
    exam = publish(client, course)
    item = begin(client, roles, exam)
    sid = item['session_id']
    assert event(client, roles, sid)[0].status_code == 200
    response = client.post(f'{ROOT}/attempts/{sid}/submit', headers=roles['student'], json={'expected_sequence': 1})
    assert response.status_code == 200, response.text
    return roles, exam, sid


def save(client, roles, sid, revision=0, score='83.25', comment='人工评阅'):
    return client.put(f'{ROOT}/attempts/{sid}/grade', headers=roles['teacher'],
                      json={'revision': revision, 'score': score, 'comment': comment})


def change(client, roles, sid, action, revision):
    return client.post(f'{ROOT}/attempts/{sid}/grade/{action}', headers=roles['teacher'], json={'revision': revision})


def student_responses(client, roles, exam, sid):
    # Exercise every exam serializer reachable by a student, including retries after sealing.
    rows = []
    for path in [ROOT, ROOT + '/history', f'{ROOT}/attempts/{sid}', f'{ROOT}/attempts/{sid}/log.json']:
        response = client.get(path, headers=roles['student'])
        assert response.status_code == 200, response.text
        rows.append(response.json())
    for path, body in [(f'{ROOT}/{exam["id"]}/begin', {'fullscreen': True}),
                       (f'{ROOT}/attempts/{sid}/submit', {'expected_sequence': 1}),
                       (f'{ROOT}/attempts/{sid}/sync', {'fullscreen': False, 'events': []})]:
        response = client.post(path, headers=roles['student'], json=body)
        assert response.status_code == 200, response.text
        rows.append(response.json())
    return rows


def grade_items(value):
    if isinstance(value, dict):
        if 'grade' in value:
            yield value['grade']
        for child in value.values():
            yield from grade_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from grade_items(child)


def test_draft_confirm_release_correction_and_all_student_serializers(client, submitted, db_session):
    roles, exam, sid = submitted
    for revision, score, comment in [(0, '83.25', '第一版评语'), (3, '91.50', '尚未发布的更正')]:
        draft = save(client, roles, sid, revision, score, comment)
        assert draft.status_code == 200, draft.text
        assert draft.json()['status'] == 'draft'
        confirmed = change(client, roles, sid, 'confirm', revision + 1)
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()['status'] == 'confirmed'
        for response in student_responses(client, roles, exam, sid):
            text = json.dumps(response, ensure_ascii=False)
            assert comment not in text
            for secret in ['standard_log', 'standard_session_id', 'automatic_evaluation', 'audit', 'confirmed_by', 'source_revision']:
                assert secret not in text
            if revision == 0:
                assert 'score' not in text and list(grade_items(response)) == []
            else:
                assert all(grade['score'] == 83.25 and grade['comment'] == '第一版评语' for grade in grade_items(response))
        released = change(client, roles, sid, 'publish', revision + 2)
        assert released.status_code == 200, released.text
        expected_version = 1 if revision == 0 else 2
        for response in student_responses(client, roles, exam, sid):
            grades = list(grade_items(response))
            assert grades and all(g['score'] == float(score) and g['comment'] == comment and g['version'] == expected_version for g in grades)
            assert all(set(g) == {'score', 'comment', 'version', 'published_at'} for g in grades)
        assert change(client, roles, sid, 'publish', revision + 2).status_code == 200
    # Replay of the first publication after a correction is harmless.
    assert change(client, roles, sid, 'publish', 2).json()['published']['version'] == 2
    assert db_session.query(ExamGradePublication).count() == 2
    assert db_session.query(ExamGradeAudit).count() == 6
    detail = client.get(f'{ROOT}/attempts/{sid}', headers=roles['teacher']).json()
    assert detail['automatic_evaluation'] is None
    assert detail['question']['standard_log'] and detail['console']['events']
    assert [a['action'] for a in detail['grade']['audit']] == ['publish', 'confirm', 'save'] * 2


@pytest.mark.parametrize('score', [-1, '100.01', 101, '1.001', '1.230', 'NaN', 'Infinity', True, [], {}, 'no-score'])
def test_invalid_scores_are_rejected_without_draft_or_audit(client, submitted, db_session, score):
    roles, _, sid = submitted
    response = save(client, roles, sid, score=score)
    assert response.status_code == 422, response.text
    assert db_session.query(ExamGrade).count() == db_session.query(ExamGradeAudit).count() == 0
    assert change(client, roles, sid, 'confirm', 0).status_code == 409
    assert change(client, roles, sid, 'publish', 0).status_code == 409


@pytest.mark.parametrize('score', ['0', '100.00', '99.99'])
def test_score_boundaries_and_optional_comment(client, submitted, score):
    roles, _, sid = submitted
    assert save(client, roles, sid, score=score, comment=None).status_code == 200
    assert change(client, roles, sid, 'publish', 1).status_code == 409
    assert change(client, roles, sid, 'confirm', 1).status_code == 200
    result = change(client, roles, sid, 'publish', 2).json()
    assert result['published']['score'] == float(score) and result['published']['comment'] is None


def test_missing_score_may_save_but_not_confirm_or_publish_and_edits_reset_confirmation(client, submitted):
    roles, _, sid = submitted
    assert save(client, roles, sid, score=None).json()['score'] is None
    assert change(client, roles, sid, 'confirm', 1).status_code == 422
    assert change(client, roles, sid, 'publish', 1).status_code == 409
    assert save(client, roles, sid, 1).json()['revision'] == 2
    confirmed = change(client, roles, sid, 'confirm', 2).json()
    assert confirmed['revision'] == 3
    assert change(client, roles, sid, 'confirm', 2).json()['revision'] == 3
    edited = save(client, roles, sid, 3, '70').json()
    assert edited['status'] == 'draft' and edited['confirmed_by'] is None and edited['confirmed_at'] is None
    assert change(client, roles, sid, 'publish', 3).status_code == 409
    assert change(client, roles, sid, 'publish', 4).status_code == 409
    assert change(client, roles, sid, 'confirm', 3).status_code == 409
    assert save(client, roles, sid, 3).status_code == 409


def test_permissions_active_attempt_and_admin_handoff(client, submitted, db_session):
    roles, exam, sid = submitted
    stranger = auth_headers(client, 's6_other_teacher', 'teacher')
    for headers in [roles['student'], roles['peer'], stranger]:
        expected = 403 if headers != stranger else 404
        for method, suffix, body in [('put', '', {'revision': 0, 'score': 100}),
                                     ('post', '/confirm', {'revision': 0}), ('post', '/publish', {'revision': 0})]:
            response = getattr(client, method)(f'{ROOT}/attempts/{sid}/grade{suffix}', headers=headers, json=body)
            assert response.status_code == expected, response.text
    peer = begin(client, roles, exam, 'peer')['session_id']
    assert save(client, roles, peer).status_code == 409
    assert client.get(f'{ROOT}/attempts/{sid}', headers=roles['peer']).status_code == 404
    assert client.get(f'{ROOT}/attempts/{sid}/log.json', headers=stranger).status_code == 404
    saved = client.put(f'{ROOT}/attempts/{sid}/grade', headers=roles['admin'], json={'revision': 0, 'score': '60.01'})
    assert saved.status_code == 200, saved.text
    assert change(client, roles, sid, 'confirm', 1).status_code == 200
    response = client.post(f'{ROOT}/attempts/{sid}/grade/publish', headers=roles['admin'], json={'revision': 2})
    assert response.status_code == 200
    admin_id = db_session.scalar(select(User.id).where(User.username == 's5_admin'))
    assert db_session.query(ExamGradePublication).one().publisher_id == admin_id
    assert response.json()['audit'][0]['actor_id'] == admin_id


def test_fullscreen_violation_never_defaults_to_zero(client, course, clock, db_session):
    roles = course[0]; sid = begin(client, roles, publish(client, course))['session_id']
    sync(client, roles, sid, False, [control('exit', clock[0])])
    clock[0] += timedelta(seconds=61)
    sealed = client.get(f'{ROOT}/attempts/{sid}', headers=roles['teacher']).json()
    assert sealed['finish_reason'] == 'fullscreen_timeout'
    assert sealed['grade']['status'] == 'ungraded' and sealed['grade']['score'] is None
    assert db_session.query(ExamGrade).count() == 0
    assert save(client, roles, sid, score='88.88').status_code == 200
    assert change(client, roles, sid, 'confirm', 1).status_code == 200
    assert change(client, roles, sid, 'publish', 2).json()['published']['score'] == 88.88


def test_cross_connection_concurrent_saves_publications_and_restart(client, submitted, db_session):
    roles, _, sid = submitted
    uid = db_session.scalar(select(User.id).where(User.username == 's5_teacher'))
    factory = sessionmaker(bind=db_session.get_bind())
    def concurrent_save(score):
        try:
            with factory() as db, exams.atomic(db):
                return exam_grades.save(db, db.get(User, uid), sid, GradeDraft(revision=0, score=score))['revision']
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(concurrent_save, ['80', '90']))
    assert sorted(result) == [1, 409]
    assert change(client, roles, sid, 'confirm', 1).status_code == 200
    def concurrent_publish(_):
        with factory() as db, exams.atomic(db):
            return exam_grades.publish(db, db.get(User, uid), sid, 2)['published']
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(concurrent_publish, range(2)))
    assert result[0] == result[1]
    with factory() as db:
        assert db.query(ExamGradePublication).count() == 1
        assert db.query(ExamGradeAudit).count() == 3
        student = db.scalar(select(User).where(User.username == 's5_student'))
        assert exams.get_detail(db, student, sid)['grade'] == result[0]


def test_comment_and_unknown_fields_rejected_and_grade_cannot_enter_learning(client, submitted):
    roles, _, sid = submitted
    assert save(client, roles, sid, comment='x' * 4001).status_code == 422
    for body in [{'revision': 0, 'score': 80, 'automatic_evaluation': 100}, {'revision': True, 'score': 80}]:
        assert client.put(f'{ROOT}/attempts/{sid}/grade', headers=roles['teacher'], json=body).status_code == 422
    assert client.get(f'/api/operation-learning/attempts/{sid}', headers=roles['teacher']).status_code == 404
