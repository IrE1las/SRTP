import copy
import csv
import io
import pytest
from app.models import LabQuestion,LabAttempt,QuestionWorkspace,GradeAudit
from app.services.lab_topics import import_topics,evaluate
from tests.test_exercise_api import auth_headers
from tests.test_shunting_questions import _import_payload


@pytest.fixture()
def setup(client,db_session):
    _import_payload(db_session);import_topics(db_session);db_session.commit()
    return {'admin':auth_headers(client,'author_admin','admin'),'teacher':auth_headers(client,'author_teacher','teacher'),
            'student':auth_headers(client,'author_student','student'),'other':auth_headers(client,'author_other','student')}


def content():
    return {'title':'自编评分测试','topic':9,'sequence':1,'level':'基础','prompt':'根据原图解释道岔锁闭。',
            'conditions':[],'source_section':'实验1单锁与封闭','devices':['1/3'],'diagram_mode':'station','fields':[
        {'id':'choose','kind':'multi','label':'多项辨析','points':10,'options':['甲','乙','丙'],'expected':['甲','乙'],'scoring':'partial','explanation':'甲和乙对应给定条件。'},
        {'id':'cell','kind':'cell','label':'填写符号','points':10,'expected':'{23/25}','accepted_answers':[],'matching':'tokens','explanation':'大括号表示带动。'},
        {'id':'reason','kind':'essay','label':'原因分析','points':10,'criteria':['区分状态','说明依据'],'rubric':[{'id':'state','label':'区分状态','points':4},{'id':'evidence','label':'说明依据','points':6}]}]}


def create(client,auth,payload=None):
    r=client.post('/api/management/questions',headers=auth,json={'content':payload or content()});assert r.status_code==201,r.text
    return r.json()


def publish(client,auth,q):
    r=client.post(f"/api/management/questions/{q['id']}/publish",headers=auth,json={'revision':q['revision']});assert r.status_code==200,r.text
    return r.json()


def submit(client,auth,key,answers=None):
    q=client.get(f'/api/lab-topics/questions/{key}',headers=auth).json()
    r=client.post(f'/api/lab-topics/questions/{key}/submit',headers=auth,json={'fingerprint':q['fingerprint'],'answers':answers or {'choose':['甲'],'cell':'{23/25}','reason':'解释占用与锁闭，并提供实验依据。'}})
    assert r.status_code==201,r.text
    return r.json()


def marking(detail):
    return {'etag':detail['etag'],'scores':{'reason':8},'rubric_scores':{'reason':{'state':4,'evidence':4}},
            'field_comments':{'reason':'已正确区分状态，请补充具体实验。'},'comment':'条件分析清楚，补充记录。','reason':''}


def test_authoring_permissions_and_draft_visibility(client,setup,db_session):
    assert client.get('/api/management/questions').status_code==401
    for role in ['student','teacher']:
        assert client.post('/api/management/questions',headers=setup[role],json={'content':content()}).status_code==403
        assert client.get('/api/management/questions',headers=setup[role]).status_code==403
    q=create(client,setup['admin'])
    assert q['status']=='draft' and q['published_version']==0
    assert client.get('/api/lab-topics/questions/'+q['key'],headers=setup['student']).status_code==404
    assert len(client.get('/api/lab-topics/questions',headers=setup['student']).json())==24
    live=publish(client,setup['admin'],q)
    assert live['status']=='published' and live['published_version']==1
    public=client.get('/api/lab-topics/questions/'+q['key'],headers=setup['student']).json()
    assert public['topic_info']['title']=='自主命题'
    assert public['diagram_mode']=='station'
    assert all(not set(f)&{'expected','rubric','criteria','accepted_answers'} for f in public['fields'])
    assert len(client.get('/api/lab-topics/questions',headers=setup['student']).json())==25


def test_published_edits_versions_and_old_attempts_remain_unchanged(client,setup,db_session):
    q=create(client,setup['admin']);live=publish(client,setup['admin'],q)
    answer=submit(client,setup['student'],q['key'])
    original=db_session.get(LabAttempt,answer['id']).question_snapshot
    original=copy.deepcopy(original)
    old_public=client.get('/api/lab-topics/questions/'+q['key'],headers=setup['student']).json()
    edited=content();edited['title']='改版后的题目';edited['fields'][0]['expected']=['丙']
    draft=client.put(f"/api/management/questions/{q['id']}/draft",headers=setup['admin'],json={'revision':live['revision'],'content':edited}).json()
    assert client.get('/api/lab-topics/questions/'+q['key'],headers=setup['student']).json()['title']=='自编评分测试'
    assert client.put(f"/api/management/questions/{q['id']}/draft",headers=setup['admin'],json={'revision':live['revision'],'content':edited}).status_code==409
    latest=publish(client,setup['admin'],draft)
    assert latest['published_version']==2
    stale=client.post('/api/lab-topics/questions/'+q['key']+'/submit',headers=setup['student'],json={'fingerprint':old_public['fingerprint'],'answers':answer['answers']})
    assert stale.status_code==409
    db_session.expire_all()
    assert db_session.get(LabAttempt,answer['id']).question_snapshot==original
    history=client.get(f"/api/management/questions/{q['id']}/versions",headers=setup['admin']).json()
    assert [h['version'] for h in history]==[2,1]
    restored=client.post(f"/api/management/questions/{q['id']}/versions/1/restore",headers=setup['admin'],json={'revision':latest['revision']}).json()
    assert restored['content']['title']=='自编评分测试'
    assert client.get('/api/lab-topics/questions/'+q['key'],headers=setup['student']).json()['title']=='改版后的题目'


def test_clone_pause_and_atomic_bulk_conflict(client,setup,db_session):
    a=create(client,setup['admin']);a=publish(client,setup['admin'],a)
    b=client.post(f"/api/management/questions/{a['id']}/clone",headers=setup['admin']).json()
    assert b['status']=='draft' and b['key']!=a['key']
    b=publish(client,setup['admin'],b)
    bulk={'items':[{'id':a['id'],'revision':a['revision']},{'id':b['id'],'revision':b['revision']-1}],'status':'archived'}
    assert client.post('/api/management/questions/bulk-status',headers=setup['admin'],json=bulk).status_code==409
    db_session.rollback();db_session.expire_all()
    assert db_session.get(QuestionWorkspace,a['id']).status=='published'
    bulk['items'][1]['revision']=b['revision']
    assert client.post('/api/management/questions/bulk-status',headers=setup['admin'],json=bulk).status_code==200
    assert client.get('/api/lab-topics/questions/'+a['key'],headers=setup['student']).status_code==404


@pytest.mark.parametrize('problem',['rubric_total','bad_expected','duplicate_options','unknown_device','missing_prompt','interval_conditions','zero_points'])
def test_publish_rejects_invalid_grading_definition(client,setup,problem):
    value=content()
    if problem=='rubric_total':value['fields'][2]['rubric'][0]['points']=3
    elif problem=='bad_expected':value['fields'][0]['expected']=['丁']
    elif problem=='duplicate_options':value['fields'][0]['options']=['甲','甲']
    elif problem=='unknown_device':value['devices']=['不存在的站内设备']
    elif problem=='missing_prompt':value['prompt']=''
    elif problem=='interval_conditions':value['diagram_mode']='auto'
    else:value['fields'][2]['points']=0
    r=client.post('/api/management/preview',headers=setup['admin'],json={'content':value})
    assert r.status_code==422,r.text


def test_preview_partial_credit_aliases_and_no_persistent_attempt(client,setup,db_session):
    value=content();value['fields'][1]['matching']='text';value['fields'][1]['accepted_answers']=['带动23/25']
    answers={'choose':['甲'],'cell':'带动23/25','reason':'推理与依据'}
    r=client.post('/api/management/preview',headers=setup['admin'],json={'content':value,'answers':answers})
    assert r.status_code==200,r.text
    assert r.json()['result']['automatic_score']==15
    assert r.json()['result']['feedback'][0]['status']=='partial'
    assert db_session.query(LabAttempt).count()==0
    answers['choose']=['甲','丙']
    assert client.post('/api/management/preview',headers=setup['admin'],json={'content':value,'answers':answers}).json()['result']['automatic_score']==10


def test_grade_drafts_rubrics_regrade_conflicts_and_audit(client,setup,db_session):
    q=create(client,setup['admin']);publish(client,setup['admin'],q);a=submit(client,setup['student'],q['key'])
    path=f"/api/management/reviews/{a['id']}"
    assert client.get(path,headers=setup['student']).status_code==403
    d=client.get(path,headers=setup['teacher']).json();body=marking(d)
    draft={'content':body}
    assert client.put(path+'/draft',headers=setup['teacher'],json=draft).status_code==200
    assert client.get(path,headers=setup['admin']).json()['draft'] is None
    own=client.get('/api/lab-topics/attempts',headers=setup['student']).json()[0]
    assert own['review'] is None and own['result']['total_score'] is None
    invalid=copy.deepcopy(body);invalid['scores']['reason']=9
    assert client.post(path+'/grade',headers=setup['teacher'],json=invalid).status_code==422
    invalid=copy.deepcopy(body);invalid['rubric_scores']['reason']['state']=True
    assert client.post(path+'/grade',headers=setup['teacher'],json=invalid).status_code==422
    graded=client.post(path+'/grade',headers=setup['teacher'],json=body)
    assert graded.status_code==200,graded.text
    assert graded.json()['result']['total_score']==23
    assert graded.json()['draft'] is None and len(graded.json()['audit'])==1
    assert client.post(path+'/grade',headers=setup['admin'],json=body).status_code==409
    revised=marking(graded.json());revised['scores']['reason']=10;revised['rubric_scores']['reason']['evidence']=6
    assert client.post(path+'/grade',headers=setup['admin'],json=revised).status_code==422
    revised['reason']='复核后补记实验依据得分'
    final=client.post(path+'/grade',headers=setup['admin'],json=revised)
    assert final.status_code==200,final.text
    assert final.json()['result']['total_score']==25 and len(final.json()['audit'])==2
    assert db_session.query(GradeAudit).count()==2
    saved=client.get('/api/lab-topics/attempts',headers=setup['student']).json()[0]
    assert saved['review']['field_comments']['reason']==body['field_comments']['reason']


def test_queue_filters_latest_attempt_and_safe_csv(client,setup,db_session):
    q=create(client,setup['admin']);publish(client,setup['admin'],q)
    a=submit(client,setup['student'],q['key']);b=submit(client,setup['student'],q['key']);submit(client,setup['other'],q['key'])
    latest=client.get('/api/management/reviews',headers=setup['teacher']).json()
    assert latest['total']==2 and a['id'] not in [x['id'] for x in latest['items']]
    assert client.get('/api/management/reviews?latest_only=false',headers=setup['teacher']).json()['total']==3
    assert client.get('/api/management/reviews?search=author_student',headers=setup['teacher']).json()['total']==1
    assert client.get('/api/management/reviews?topic=1',headers=setup['teacher']).json()['total']==0
    from app.models import User
    u=db_session.query(User).filter_by(username='author_student').one();u.real_name='=1+1';db_session.commit()
    response=client.get('/api/management/reviews/export?latest_only=true',headers=setup['teacher'])
    assert response.status_code==200
    rows=list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert len(rows)==3
    assert any(row[2]=="'=1+1" for row in rows[1:])
    assert all(row[9]=='' for row in rows[1:])
    assert client.get('/api/management/reviews/export',headers=setup['student']).status_code==403


def test_personal_comment_library_is_private(client,setup):
    r=client.post('/api/management/snippets',headers=setup['teacher'],json={'text':'请补充实验依据。'})
    assert r.status_code==201
    assert client.get('/api/management/snippets',headers=setup['admin']).json()==[]
    assert client.delete('/api/management/snippets/'+str(r.json()['id']),headers=setup['admin']).status_code==404
    assert client.delete('/api/management/snippets/'+str(r.json()['id']),headers=setup['teacher']).status_code==204
