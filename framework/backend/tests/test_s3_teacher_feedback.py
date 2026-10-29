"""User feedback: shared course, real classes and deliberate question deletion."""
from sqlalchemy import func, select
from app.models import User
from app.models.operation import OperationQuestion, OperationVersion, OperationSession, OperationEvent
from tests.helpers import auth_headers
from tests.test_s3_operations import BASE, draft, start, record_standard


def test_classes_come_from_student_identities_and_are_shared_between_teachers(client, db_session):
    teacher = auth_headers(client, 'classes_teacher', 'teacher')
    other = auth_headers(client, 'classes_other', 'teacher')
    student = auth_headers(client, 'classes_student', 'student')
    auth_headers(client, 'classes_second', 'student')
    db_session.add(User(username='no_class', password_hash='not-a-login', role='student', student_id='no-class-id', class_name=' '))
    db_session.add(User(username='extra_class', password_hash='not-a-login', role='student', student_id='extra-id', class_name='信号二班'))
    db_session.commit()
    expected={'items':[{'name':'信号一班','student_count':2},{'name':'信号二班','student_count':1}],'total':2}
    assert client.get(BASE+'/classes',headers=teacher).json()==expected
    assert client.get(BASE+'/classes',headers=other).json()==expected
    assert client.get(BASE+'/classes',headers=student).status_code==403
    assert client.get(BASE+'/classes').status_code==401


def test_shared_teacher_can_edit_publish_and_download_while_old_revision_is_rejected(client):
    teacher=auth_headers(client,'share_author','teacher')
    other=auth_headers(client,'share_editor','teacher')
    q=draft(client,teacher)
    path=f"{BASE}/questions/{q['id']}"
    body={key:q[key] for key in ['title','prompt','classes','initial','revision']}
    body['title']='共同修订'
    edited=client.put(path,headers=other,json=body)
    assert edited.status_code==200
    assert client.get(path,headers=teacher).json()['title']=='共同修订'
    assert client.put(path,headers=teacher,json=body).status_code==409
    saved,session=record_standard(client,other,q['id'])
    assert client.get(f"{BASE}/sessions/{session['session_id']}/log.json",headers=teacher).status_code==200
    assert client.post(path+'/publish',headers=teacher).status_code==200
    assert client.get(path,headers=other).json()['status']=='published'


def test_delete_removes_question_versions_sessions_events_but_keeps_other_course_data(client, db_session):
    teacher=auth_headers(client,'delete_author','teacher')
    other=auth_headers(client,'delete_other','teacher')
    student=auth_headers(client,'delete_student','student')
    q=draft(client,teacher)
    keep=draft(client,other,title='保留这道题')
    saved,session=record_standard(client,teacher,q['id'])
    path=f"{BASE}/questions/{q['id']}"
    assert client.post(path+'/publish',headers=other).status_code==200
    assert client.delete(path,headers=student).status_code==403
    assert client.delete(path,headers=other).json()=={'deleted':True,'id':q['id']}
    assert client.get(path,headers=teacher).status_code==404
    assert client.get(f"{BASE}/sessions/{session['session_id']}/log.json",headers=other).status_code==404
    assert client.get(f"{BASE}/questions/{keep['id']}",headers=teacher).status_code==200
    assert client.get(BASE+'/questions',headers=student).json()['total']==0
    for model in [OperationSession,OperationEvent]:
        assert db_session.scalar(select(func.count()).select_from(model))==0
    assert db_session.scalar(select(func.count()).select_from(OperationVersion))==1
    assert db_session.scalar(select(func.count()).select_from(OperationQuestion))==1
    assert db_session.scalar(select(func.count()).select_from(User))==3
    assert client.delete(path,headers=teacher).status_code==404


def test_delete_is_blocked_until_every_active_recording_or_preview_has_ended(client):
    teacher=auth_headers(client,'active_delete_author','teacher')
    other=auth_headers(client,'active_delete_other','teacher')
    q=draft(client,teacher)
    session=start(client,teacher,q['id'],'preview')
    viewed=client.get(f"{BASE}/sessions/{session['session_id']}",headers=other)
    assert viewed.status_code==200 and viewed.json()['read_only'] is True
    assert client.post(f"{BASE}/sessions/{session['session_id']}/stop",headers=other).status_code==404
    path=f"{BASE}/questions/{q['id']}"
    assert client.delete(path,headers=other).status_code==409
    assert client.get(path,headers=other).status_code==200
    assert client.post(f"{BASE}/sessions/{session['session_id']}/stop",headers=teacher).status_code==200
    assert client.delete(path,headers=other).status_code==200
