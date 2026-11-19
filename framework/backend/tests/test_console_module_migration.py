"""One console protocol across theory, recording, learning and examination."""
from copy import deepcopy
from uuid import uuid4
import pytest
from app.core.security import create_access_token
from app.models import User, LabQuestion
from app.services.lab_topics import import_topics
from app.services.operation_runtime import pack, unpack
from app.services.simulation_console.clock import at
from app.services.simulation_console.console_station import console_station_package
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.reference_runtime import ReferenceSimulationService
from tests.test_free_console_behaviour import Rig
from tests.test_shunting_questions import _import_payload


@pytest.fixture()
def actors(db_session):
    users={}
    for role in ['student','teacher','admin']:
        user=User(username='migration-'+role,password_hash='fixture',role=role,class_name='迁移测试班')
        db_session.add(user);db_session.flush()
        users[role]={'Authorization':'Bearer '+create_access_token({'sub':str(user.id)})}
    db_session.commit()
    return users


@pytest.mark.parametrize('topic',[1,2,3,4])
def test_each_standard_theory_topic_has_the_same_devices_and_commands(client,db_session,actors,topic):
    _import_payload(db_session);import_topics(db_session);db_session.commit()
    root=f'/api/lab-topics/questions/lab-{topic:02}-01/console'
    package=client.get(root+'/station',headers=actors['student']).json()
    assert package['console_circuits'] and package['counts']['sections']==42
    assert package['buttons']==console_station_package()['buttons']
    snap=client.post(root+'/sessions',headers=actors['student'],json={}).json()
    result=client.post(root+'/sessions/'+snap['session_id']+'/commands',headers=actors['student'],json={
        'type':'SET_SWITCH_INDICATION','target':'6','version':snap['version']})
    assert result.status_code==200
    assert not result.json()['snapshot']['switches']['8']['represented']


def test_recording_device_commands_are_ordered_retriable_and_do_not_store_the_pin(client,actors):
    auth=actors['teacher']
    q=client.post('/api/operations/questions',headers=auth,json={
        'title':'设备录制','prompt':'办理引导。','classes':['迁移测试班']}).json()
    session=client.post(f"/api/operations/questions/{q['id']}/sessions",headers=auth,json={'kind':'recording'}).json()
    url='/api/operations/sessions/'+session['session_id']+'/events'
    def send(command,target,params=None):
        nonlocal session
        body={'event_id':str(uuid4()),'sequence':session['revision']+1,'action':'command',
              'button_id':command,'target_id':target,'target_kind':'switch','parameters':params or {}}
        reply=client.post(url,headers=auth,json=body)
        assert reply.status_code==200,reply.text
        session=reply.json();return body
    body=send('SET_SWITCH_INDICATION','6')
    assert not session['snapshot']['switches']['8']['represented']
    repeated=client.post(url,headers=auth,json=body).json()
    assert repeated['revision']==1
    send('RESTORE_SWITCH_INDICATION','8',{'position':0})
    assert session['snapshot']['switches']['6']['represented']
    assert 'pin' not in str(session['events'])
    invalid={**body,'event_id':str(uuid4()),'sequence':3,'parameters':{'client_score':100}}
    assert client.post(url,headers=auth,json=invalid).status_code==422


def test_terminal_alias_and_train_timers_survive_rehydration():
    rig=Rig()
    with rig.clock():
        rig.service.select_button(rig.session.id,31,'D1DA')
        result=rig.service.select_button(rig.session.id,31,'D15DA')
        stored=pack(rig.service,rig.session.id)
        engine,session=unpack(console_station_package(),stored)
        assert engine.routes[session.routes[result['snapshot']['routes'][0]['id']]['route_id']]['name']=='D1>D15'
    rig=Rig();iid=rig.open('L_X>SI')
    rig.command('SIMULATE_TRAIN_START','IAG',{'route_instance_id':iid})
    rig.advance(8)
    with rig.clock():
        stored=pack(rig.service,rig.session.id)
        engine,session=unpack(console_station_package(),stored)
        assert session.routes[iid]['auto_due']==pytest.approx(rig.session.routes[iid]['auto_due'])
        assert engine._state(session)['clearing_sections']==pytest.approx(rig.service._state(rig.session)['clearing_sections'])
        assert engine.snapshot(session.id,31)['switches']==rig.service.snapshot(rig.session.id,31)['switches']


def test_legacy_record_is_adapted_without_mutating_the_original_log_state():
    with at(1000):
        old=ReferenceSimulationService(reference_station_package());snap=old.new_session(31)
        old.select_button(snap['session_id'],31,'D3DA');old.select_button(snap['session_id'],31,'D7DA')
        stored=pack(old,snap['session_id']);before=deepcopy(stored)
        engine,session=unpack(console_station_package(),stored)
        assert len(session.sections)==42
        assert next(iter(session.routes.values()))['sections']==['5DG','3DG']
        assert stored==before
        assert len(engine.snapshot(session.id,31)['sections'])==42


def test_new_experiment_fields_have_authored_answers_and_manual_analysis(db_session):
    _import_payload(db_session);import_topics(db_session)
    questions=[q for q in db_session.query(LabQuestion) if int(q.key[-2:])>=4 and q.topic<=2]
    assert len(questions)==16
    assert sum(f['kind']=='choice' for q in questions for f in q.content['fields'])==61
    assert all(any(f['kind']=='essay' and f.get('explanation') for f in q.content['fields']) for q in questions)


@pytest.mark.parametrize('before,after',[
    ({'action':'target','button_id':'SWITCH_SINGLE_LOCK','target_id':'5','parameters':{'target_kind':'switch'}},
     {'action':'command','button_id':'SWITCH_SINGLE_LOCK','target_id':'5','parameters':{'target_kind':'switch'}}),
    ({'action':'button','button_id':'D7LA','target_id':'D7','parameters':{}},
     {'action':'button','button_id':'D7DA','target_id':'D7','parameters':{}}),
])
def test_compatible_old_and_current_click_protocols_compare_without_rewriting_logs(before,after):
    from app.services.operation_comparison import compare
    original=deepcopy(before)
    assert compare([before],[after])['status']=='correct'
    assert before==original
