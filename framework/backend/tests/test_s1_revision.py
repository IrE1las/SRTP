"""S1 acceptance revision: separate platforms and roster-first grading."""
import json
import pytest
from app.models import LabQuestion,LabAttempt,User
from app.services.bootstrap import seed_theory
from app.api import theory_console
from tests.helpers import auth_headers
from tests.test_lab_topics import completed

@pytest.fixture()
def setup(client,db_session,monkeypatch):
    seed_theory(db_session)
    monkeypatch.setattr(theory_console,'store',theory_console.TheoryConsoleStore())
    return {role:auth_headers(client,'r1_'+role,role) for role in ['student','teacher','admin']}

def root(key='lab-01-01'):
    return '/api/lab-topics/questions/'+key+'/console'

@pytest.mark.parametrize('topic',range(1,7))
def test_only_topics_one_to_four_use_the_operational_console(client,setup,topic):
    url=root(f'lab-{topic:02d}-01')
    student=setup['student']
    package=client.get(url+'/station',headers=student)
    if topic<=4:
        assert package.status_code==200
        assert package.json()['profile']=='reference'
        assert package.json()['counts']['sections']==35
        assert 'routes' not in package.json() and 'source' not in package.json()
        assert client.post(url+'/sessions',headers=student,json={}).json()['profile']=='reference'
    else:
        assert package.status_code==404
        assert client.post(url+'/sessions',headers=student,json={}).status_code==404
    assert client.get(url+'/station').status_code==401

def test_console_is_bound_to_both_question_and_owner_and_reset_invalidates_only_that_console(client,setup):
    student=setup['student'];other=auth_headers(client,'r1_other','student')
    url=root()
    first=client.post(url+'/sessions',headers=student,json={}).json()
    second=client.post(root('lab-02-01')+'/sessions',headers=student,json={}).json()
    sid=first['session_id']
    assert client.get(url+'/sessions/'+sid,headers=other).status_code==409
    assert client.get(root('lab-02-01')+'/sessions/'+sid,headers=student).status_code==409
    assert client.post(root('lab-02-01')+'/sessions/'+sid+'/buttons',headers=student,
                       json={'button':'D3DA','version':first['version']}).status_code==409
    reset=client.post(url+'/sessions',headers=student,json={}).json()
    assert reset['session_id']!=sid
    assert client.get(url+'/sessions/'+sid,headers=student).status_code==409
    assert client.get(root('lab-02-01')+'/sessions/'+second['session_id'],headers=student).status_code==200
    assert client.post(url+'/sessions',headers=student,json={'source':'workbook'}).status_code==422
    assert client.get('/api/simulation-console/station',headers=student).status_code==404

def test_operational_commands_rejections_faults_and_version_guard_work_without_creating_an_answer(client,setup,db_session):
    auth=setup['student'];url=root()
    snap=client.post(url+'/sessions',headers=auth,json={}).json()
    session=url+'/sessions/'+snap['session_id']
    def command(kind,target,**extra):
        nonlocal snap
        response=client.post(session+'/commands',headers=auth,
                             json={'type':kind,'target':target,'version':snap['version'],**extra})
        assert response.status_code==200,response.text
        result=response.json();snap=result['snapshot']
        return result
    assert command('SWITCH_SINGLE_LOCK','5')['accepted']
    assert snap['switches']['5']['manual_locked']
    assert not command('SWITCH_TOTAL_REVERSE','5')['accepted']
    assert command('SWITCH_SINGLE_UNLOCK','5')['accepted']
    assert command('SWITCH_TOTAL_REVERSE','5')['accepted']
    assert snap['switches']['5']['moving']
    assert command('SET_SECTION_OCCUPANCY','5G',payload={'kind':'vehicle'})['accepted']
    assert snap['sections']['5G']['occupied']
    assert command('CLEAR_SECTION_OCCUPANCY','5G')['accepted']
    assert not snap['sections']['5G']['occupied']
    assert command('SIGNAL_LIGHT_OFF','D3',pin='r1-sensitive-example')['reason_code']=='INVALID_PIN'
    replay=client.get(session+'/replay',headers=auth)
    assert replay.status_code==200 and replay.json()
    assert 'r1-sensitive-example' not in replay.text
    assert client.post(session+'/buttons',headers=auth,json={'button':'D3DA','version':0}).status_code==409
    assert client.post(session+'/commands',headers=auth,json={'type':'UNSUPPORTED','target':'5','version':snap['version']}).status_code==422
    assert db_session.query(LabAttempt).count()==0

def test_station_buttons_and_clear_selection_are_live_http_operations(client,setup):
    url=root();auth=setup['student']
    snap=client.post(url+'/sessions',headers=auth,json={}).json()
    path=url+'/sessions/'+snap['session_id']
    first=client.post(path+'/buttons',headers=auth,json={'button':'D3DA','version':snap['version']}).json()
    assert first['accepted']
    assert first['snapshot']['selected_buttons']==['D3DA']
    cleared=client.post(path+'/clear-selection',headers=auth,json={'version':first['snapshot']['version']}).json()
    assert cleared['snapshot']['selected_buttons']==[]
    assert client.post(url+'/sessions',headers=auth,json={'occupied_sections':['not-a-section']}).status_code==409
    assert client.get(path,headers=auth).status_code==200

def test_theory_student_can_advance_simulated_train_after_route_signal_opens(client,setup,monkeypatch):
    from app.services.simulation_console import runtime,reference_runtime,console_commands
    clock=[1000.]
    for module in (runtime,reference_runtime,console_commands):
        monkeypatch.setattr(module,'monotonic',lambda:clock[0])
    auth=setup['student'];url=root('lab-03-01')
    snap=client.post(url+'/sessions',headers=auth,json={}).json()
    path=url+'/sessions/'+snap['session_id']
    for button in ['D3DA','D7DA']:
        result=client.post(path+'/buttons',headers=auth,json={'button':button,'version':snap['version']}).json()
        assert result['accepted']
        snap=result['snapshot']
    clock[0]+=2.1
    snap=client.get(path,headers=auth).json()
    clock[0]+=.7
    snap=client.get(path,headers=auth).json()
    assert snap['signals']['D3']['aspect']=='B'
    advanced=client.post(path+'/advance',headers=auth,
                         json={'route_instance_id':snap['routes'][0]['id'],'version':snap['version']})
    assert advanced.status_code==200 and advanced.json()['accepted']

def submit(client,auth,db,key='lab-01-01'):
    question=db.query(LabQuestion).filter_by(key=key).one()
    response=client.post('/api/lab-topics/questions/'+key+'/submit',headers=auth,
                         json={'fingerprint':question.fingerprint,'answers':completed(question)})
    assert response.status_code==201
    return response.json()

def test_roster_and_student_attempt_lists_do_not_contain_answers_then_single_review_can_be_graded(client,setup,db_session):
    student=setup['student'];teacher=setup['teacher']
    other=auth_headers(client,'r1_other_student','student')
    empty=auth_headers(client,'r1_empty_student','student')
    first=submit(client,student,db_session)
    submit(client,student,db_session,'lab-02-01')
    submit(client,other,db_session)
    person=db_session.query(User).filter_by(username='r1_student').one()
    roster=client.get('/api/lab-topics/review-students',headers=teacher)
    assert roster.status_code==200
    assert len(roster.json())==3
    row=next(r for r in roster.json() if r['id']==person.id)
    assert row['attempt_count']==row['pending_count']==2
    assert next(r for r in roster.json() if r['username']=='r1_empty_student')['attempt_count']==0
    for response in [roster,client.get(f'/api/lab-topics/review-students/{person.id}/attempts',headers=teacher)]:
        assert all(word not in response.text for word in ['"answers"','"feedback"','"fields"','"expected"','password_hash'])
    summary=client.get(f'/api/lab-topics/review-students/{person.id}/attempts',headers=teacher,
                       params={'topic':1}).json()
    assert [r['id'] for r in summary['attempts']]==[first['id']]
    detail=client.get('/api/lab-topics/review-attempts/'+str(first['id']),headers=teacher).json()
    assert detail['answers']==first['answers']
    assert detail['student']['id']==person.id
    graded=client.post('/api/lab-topics/attempts/'+str(first['id'])+'/review',headers=teacher,
                       json={'scores':{'reason':8},'comment':'S1返修批改验证'})
    assert graded.status_code==200 and graded.json()['result']['total_score']==48
    after=client.get('/api/lab-topics/review-students',headers=teacher,params={'topic':1}).json()
    assert next(r for r in after if r['id']==person.id)['pending_count']==0
    refreshed=client.get('/api/lab-topics/attempts',headers=student,params={'topic':1}).json()
    assert refreshed[0]['review']['comment']=='S1返修批改验证'

@pytest.mark.parametrize('path',[
    '/api/lab-topics/review-students','/api/lab-topics/review-students/1/attempts',
    '/api/lab-topics/review-attempts/1',
])
def test_students_cannot_access_teacher_roster_lists_or_review_detail(client,setup,path):
    assert client.get(path,headers=setup['student']).status_code==403
    assert client.get(path).status_code==401

def test_missing_students_attempts_and_out_of_scope_topics_are_rejected(client,setup):
    teacher=setup['teacher']
    assert client.get('/api/lab-topics/review-students/999999/attempts',headers=teacher).status_code==404
    assert client.get('/api/lab-topics/review-attempts/999999',headers=teacher).status_code==404
    assert client.get('/api/lab-topics/review-students',headers=teacher,params={'topic':7}).status_code==422
