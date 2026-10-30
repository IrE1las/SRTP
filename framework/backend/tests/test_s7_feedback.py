"""User-approved force deletion and atomic publication, using isolated fixtures only."""
from pathlib import Path
import pytest
from sqlalchemy import select, text

from app.models import User
from app.models.operation import OperationQuestion, OperationSession
from app.models.operation_learning import OperationAttempt, OperationReview
from app.models.exam import Exam, ExamAttempt
from app.models.exam_grade import ExamGrade, ExamGradePublication, ExamGradeAudit
from app.schemas.exam_grade import GradeDraft
from app.services import exam_grades as grades, operations as ops
from tests.helpers import auth_headers
from tests.test_s5_exams import course, clock, publish, begin
from tests.test_s6_grades import submitted
from tests.test_s3_operations import draft, record_standard
from tests.test_s7_delivery import database_rows


def release(client, roles, sid, revision=0, score='86.50', comment='直接发布'):
    return client.post(f'/api/exams/attempts/{sid}/grade/publish', headers=roles['teacher'],
                       json={'revision': revision, 'score': score, 'comment': comment})


@pytest.mark.parametrize('score', ['0', '100.00', '86.50'])
def test_current_inputs_publish_atomically_with_audit_and_idempotent_retry(client, submitted, db_session, score):
    roles, _, sid = submitted
    response = release(client, roles, sid, score=score)
    assert response.status_code == 200, response.text
    assert response.json()['published']['score'] == float(score)
    assert db_session.query(ExamGradeAudit).count() == 3
    assert [r.action for r in db_session.scalars(select(ExamGradeAudit).order_by(ExamGradeAudit.revision))] == ['save', 'confirm', 'publish']
    assert release(client, roles, sid, score=score).status_code == 200
    assert db_session.query(ExamGradePublication).count() == 1
    assert release(client, roles, sid, score=score, comment='同一旧版本的新内容').status_code == 409
    assert release(client, roles, sid, revision=3, score='91.25', comment='更正').status_code == 200
    assert release(client, roles, sid, score=score).json()['published']['version'] == 2
    student = client.get(f'/api/exams/attempts/{sid}', headers=roles['student']).json()
    assert student['grade']['score'] == 91.25 and student['grade']['comment'] == '更正'
    assert db_session.query(ExamGradePublication).count() == 2


@pytest.mark.parametrize('score', [None, '', '0http:/', '-1', '100.01', '1.234', True])
def test_invalid_publication_never_creates_draft_confirmation_or_publication(client, submitted, db_session, score):
    roles, _, sid = submitted
    assert release(client, roles, sid, score=score).status_code == 422
    assert db_session.query(ExamGrade).count() == db_session.query(ExamGradePublication).count() == db_session.query(ExamGradeAudit).count() == 0


def test_publication_failure_rolls_back_save_and_confirmation(client, submitted, db_session, monkeypatch):
    roles, _, sid = submitted
    original = grades.audit
    def fail_on_publish(db, grade, user, action):
        if action == 'publish':
            ops.fail('injected publication failure')
        return original(db, grade, user, action)
    monkeypatch.setattr(grades, 'audit', fail_on_publish)
    assert release(client, roles, sid).status_code == 409
    assert db_session.query(ExamGrade).count() == db_session.query(ExamGradePublication).count() == db_session.query(ExamGradeAudit).count() == 0


def test_publication_respects_owner_student_and_active_attempt_boundaries(client, course):
    roles, _, _ = course
    sid = begin(client, roles, publish(client, course))['session_id']
    assert release(client, roles, sid).status_code == 409
    other = auth_headers(client, 's7-feedback-other', 'teacher')
    body = {'revision': 0, 'score': '80'}
    assert client.post(f'/api/exams/attempts/{sid}/grade/publish', headers=other, json=body).status_code == 404
    assert client.post(f'/api/exams/attempts/{sid}/grade/publish', headers=roles['student'], json=body).status_code == 403


@pytest.fixture()
def linked(client, submitted, course, db_session):
    roles, exam, sid = submitted
    q = course[1]
    assert release(client, roles, sid).status_code == 200
    response = client.post(f"/api/operation-learning/questions/{q['id']}/begin", headers=roles['student'], json={})
    assert response.status_code == 200, response.text
    learning = response.json()['session_id']
    assert client.post(f'/api/operation-learning/attempts/{learning}/submit', headers=roles['student'], json={}).status_code == 200
    review = db_session.get(OperationReview, learning)
    review.comment = '将随题目删除的评语'
    db_session.commit()
    # This live attempt is also explicitly included in the force-delete preview/confirmation.
    peer = begin(client, roles, exam, 'peer')['session_id']
    return roles, q, sid, learning, peer


def test_force_delete_requires_disabled_question_and_manager_and_preview_is_read_only(client, linked, db_session):
    roles, q, _, _, _ = linked
    path = f"/api/operations/questions/{q['id']}"
    before = database_rows(Path(db_session.get_bind().url.database))
    preview = client.get(path + '/deletion', headers=roles['teacher'])
    assert preview.status_code == 200, preview.text
    assert preview.json()['learning_attempts'] == preview.json()['exams'] == preview.json()['grade_publications'] == 1
    assert preview.json()['exam_attempts'] == 2
    assert client.get(path + '/deletion', headers=roles['student']).status_code == 403
    assert client.delete(path, headers=roles['student'], params={'force': True}).status_code == 403
    assert client.delete(path, headers=roles['teacher'], params={'force': True}).status_code == 409
    assert database_rows(Path(db_session.get_bind().url.database)) == before


def test_force_delete_clears_all_linked_history_and_leaves_other_questions_exams_and_accounts(client, linked, course, db_session):
    roles, q, sid, learning, peer = linked
    other = draft(client, roles['teacher'], title='必须保留的另一道题')
    other, _ = record_standard(client, roles['teacher'], other['id'])
    assert client.post(f"/api/operations/questions/{other['id']}/publish", headers=roles['teacher']).status_code == 200
    other_exam = publish(client, (roles, other, {**course[2], 'version_id': other['version_id']}))
    other_sid = begin(client, roles, other_exam)['session_id']
    assert client.post(f'/api/exams/attempts/{other_sid}/submit', headers=roles['student'], json={'expected_sequence': 0}).status_code == 200
    assert release(client, roles, other_sid, score='99').status_code == 200
    users = db_session.query(User).count()
    path = f"/api/operations/questions/{q['id']}"
    assert client.post(path + '/disable', headers=roles['teacher']).status_code == 200
    assert client.delete(path, headers=roles['teacher']).status_code == 409
    db_session.commit()
    db_session.execute(text('PRAGMA foreign_keys=ON'))
    db_session.commit()
    response = client.delete(path, headers=roles['teacher'], params={'force': True})
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.get(OperationQuestion, q['id']) is None
    assert db_session.get(OperationQuestion, other['id']) is not None
    for gone in (sid, learning, peer):
        assert db_session.get(OperationSession, gone) is None
    assert db_session.query(User).count() == users
    assert db_session.query(OperationAttempt).count() == db_session.query(OperationReview).count() == 0
    assert db_session.query(Exam).count() == db_session.query(ExamAttempt).count() == 1
    assert db_session.query(ExamGrade).count() == db_session.query(ExamGradePublication).count() == 1
    assert client.get(f'/api/exams/attempts/{other_sid}', headers=roles['student']).json()['grade']['score'] == 99
    assert not db_session.execute(text('PRAGMA foreign_key_check')).fetchall()
    assert client.get(f'/api/exams/attempts/{sid}', headers=roles['student']).status_code == 404
    assert client.delete(path, headers=roles['teacher'], params={'force': True}).status_code == 404


def test_force_deletion_failure_rolls_back_complete_history_graph(client, linked, db_session, monkeypatch):
    roles, q, _, _, _ = linked
    path = f"/api/operations/questions/{q['id']}"
    assert client.post(path + '/disable', headers=roles['teacher']).status_code == 200
    before = database_rows(Path(db_session.get_bind().url.database))
    original = ops.delete
    def fail_on_session(model):
        if model is OperationSession:
            raise RuntimeError('injected deletion failure')
        return original(model)
    monkeypatch.setattr(ops, 'delete', fail_on_session)
    with pytest.raises(RuntimeError, match='injected deletion failure'):
        client.delete(path, headers=roles['teacher'], params={'force': True})
    assert database_rows(Path(db_session.get_bind().url.database)) == before
