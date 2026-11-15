"""Retained learning evidence remains private; free practice is not archived."""
from copy import deepcopy
import pytest
from app.core.security import create_access_token
from app.models.user import User
from tests.test_lab_topics import topics, completed

@pytest.fixture()
def accounts(db_session):
    users=[User(username='records_'+role,password_hash='unused',role=role) for role in ('student','teacher','admin')]
    db_session.add_all(users);db_session.commit();return users

def headers(user):
    return {'Authorization':'Bearer '+create_access_token({'sub':str(user.id)})}

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
