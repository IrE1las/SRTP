"""Real station trajectories and HTTP permissions; all data are isolated."""
from datetime import timedelta
from uuid import uuid4
import json
import pytest
from sqlalchemy import select
from app.models.operation import OperationSession
from app.models.operation_assessment import ExamEvaluation, OperationEvidenceEvent, ExamEvidenceSeal
from app.services import exams
from app.services.operation_assessment import evidence, service as assessment
from tests.helpers import auth_headers
from tests.test_s3_operations import draft, start, click, BASE
from tests.test_s5_exams import clock, begin

ROOT = '/api/exams'


@pytest.fixture()
def prepared(client, clock, request):
    roles = {r: auth_headers(client, 'assessment_' + r, r) for r in ('teacher', 'student')}
    q = draft(client, roles['teacher'], title='正常接车', prompt='正常办理XD至III道接车进路并保持。')
    recorded = start(client, roles['teacher'], q['id'])
    for name in ['XDLA', 'SIIILA']:
        recorded, _ = click(client, roles['teacher'], recorded, button_id=name)
    sid = recorded['session_id']
    assert client.post(f'{BASE}/sessions/{sid}/stop', headers=roles['teacher']).status_code == 200
    assert client.post(f'{BASE}/sessions/{sid}/save-standard', headers=roles['teacher']).status_code == 200
    result = client.put(f"{BASE}/questions/{q['id']}/assessment", headers=roles['teacher'], json={
        'revision': 0, 'enabled': True, 'route_ids': ['SDM-071'], 'confirmed': True,
        **getattr(request,'param',{})})
    assert result.status_code == 200, result.text
    assert client.post(f"{BASE}/questions/{q['id']}/publish", headers=roles['teacher']).status_code == 200
    body = {'name': '接车评价测试', 'version_id': q['version_id'], 'classes': ['信号一班'],
            'opens_at': exams.iso(clock[0]), 'closes_at': exams.iso(clock[0] + timedelta(minutes=10)), 'duration_minutes': 5}
    result = client.post(ROOT, headers=roles['teacher'], json=body)
    assert result.status_code == 200, result.text
    exam = result.json()
    result = client.post(f"{ROOT}/{exam['id']}/publish", headers=roles['teacher'], json={'revision': exam['revision']})
    assert result.status_code == 200, result.text
    attempt = begin(client, roles, result.json())
    return roles, q, attempt


def send(client, prepared, action='button', **values):
    roles, _, attempt = prepared
    payload = {'event_id': str(uuid4()), 'sequence': attempt['console']['revision'] + 1, 'action': action, **values}
    response = client.post(f"{ROOT}/attempts/{attempt['session_id']}/events", headers=roles['student'], json=payload)
    assert response.status_code == 200, response.text
    attempt['console'] = response.json()
    return response.json(), payload


def route(client, prepared, destination='SIIILA'):
    send(client, prepared, button_id='XDLA')
    send(client, prepared, button_id=destination)


def wait(client, prepared, clock, seconds):
    clock[0] += timedelta(seconds=seconds)
    roles, _, attempt = prepared
    response = client.post(f"{ROOT}/attempts/{attempt['session_id']}/sync", headers=roles['student'],
                           json={'fullscreen': True, 'events': []})
    assert response.status_code == 200, response.text
    attempt.update(response.json())


def finish(client, prepared):
    roles, _, attempt = prepared
    response = client.post(f"{ROOT}/attempts/{attempt['session_id']}/submit", headers=roles['student'],
                           json={'expected_sequence': attempt['console']['revision']})
    assert response.status_code == 200, response.text
    assert 'automatic_evaluation' not in response.json()
    result = client.get(f"{ROOT}/attempts/{attempt['session_id']}", headers=roles['teacher'])
    assert result.status_code == 200, result.text
    evaluation = result.json()['automatic_evaluation']
    assert evaluation is not None
    return evaluation


@pytest.mark.parametrize('scenario,expected', [('normal',100), ('clear',98), ('timeout',98),
    ('reject',95), ('wrong_locked',90), ('wrong_open',80), ('cancel_target',59), ('empty',0)])
def test_station_trajectories(client, prepared, clock, scenario, expected, db_session):
    if scenario == 'clear':
        send(client, prepared, button_id='D3DA')
        send(client, prepared, 'function', button_id='CLEAR_SELECTION')
    if scenario == 'timeout':
        send(client, prepared, button_id='XDLA')
        wait(client, prepared, clock, 16)
    if scenario == 'reject':
        send(client, prepared, button_id='XDLA')
        send(client, prepared, button_id='D3DA')
    if scenario in {'wrong_locked', 'wrong_open'}:
        route(client, prepared, 'S5LA')
        if scenario == 'wrong_open':
            wait(client, prepared, clock, 3)
        send(client, prepared, 'function', button_id='CANCEL_ROUTE')
        send(client, prepared, 'target', target_id='XD', target_kind='signal')
        wait(client, prepared, clock, 4)
    if scenario != 'empty':
        route(client, prepared)
        wait(client, prepared, clock, 3)
    if scenario == 'cancel_target':
        send(client, prepared, 'function', button_id='CANCEL_ROUTE')
        send(client, prepared, 'target', target_id='XD', target_kind='signal')
        wait(client, prepared, clock, 1)
    evaluation = finish(client, prepared)
    assert evaluation['status'] == 'ready', evaluation
    assert evaluation['suggested_score'] == expected, evaluation
    if scenario in {'wrong_locked','wrong_open'}:
        assert len(evaluation['episodes']) == 1, evaluation
        assert evaluation['episodes'][0]['recovered'] is True
    record = db_session.get(OperationSession, prepared[2]['session_id'])
    assert 'runtime_events' not in record.engine_state
    assert len(record.engine_state['session']['events']) <= 10


def test_late_settlement_advances_to_deadline_not_observation(client, prepared, clock):
    roles, _, attempt = prepared
    route(client, prepared)
    # The signal needs 0.6s, but the exam's original deadline is still far away.
    deadline = exams.utc(__import__('datetime').datetime.fromisoformat(attempt['deadline']))
    clock[0] = deadline + timedelta(seconds=20)
    result = client.get(f"{ROOT}/attempts/{attempt['session_id']}", headers=roles['teacher']).json()
    assert result['automatic_evaluation']['suggested_score'] == 100, result
    assert result['automatic_evaluation']['cutoff_at'] == attempt['deadline']


def test_signal_due_after_manual_cutoff_is_not_counted(client, prepared):
    route(client, prepared)
    result = finish(client, prepared)
    assert result['milestones']['A3'] is False
    assert result['suggested_score'] == 59


def test_retry_is_idempotent_and_light_sync_does_not_load_history(client, prepared, clock, db_session):
    roles, _, attempt = prepared
    first, payload = send(client, prepared, button_id='XDLA')
    sid = attempt['session_id']
    count = db_session.query(OperationEvidenceEvent).filter_by(session_id=sid).count()
    duplicate = client.post(f'{ROOT}/attempts/{sid}/events', headers=roles['student'], json=payload)
    assert duplicate.status_code == 200
    assert db_session.query(OperationEvidenceEvent).filter_by(session_id=sid).count() == count
    state_revision = db_session.get(OperationSession,sid).state_revision
    response = client.post(f'{ROOT}/attempts/{sid}/sync', headers=roles['student'], json={
        'fullscreen':True,'events':[], 'after_sequence':1,'state_version':first['snapshot']['version']})
    assert response.status_code == 200, response.text
    value=response.json()
    assert value['console']['snapshot'] is None
    assert value['console']['events'] == []
    assert db_session.get(OperationSession,sid).state_revision == state_revision
    assert len(response.content) < 4096


def test_evidence_tampering_and_permissions(client, prepared, clock, db_session):
    route(client, prepared); wait(client, prepared, clock, 3)
    sid = prepared[2]['session_id']
    row = db_session.scalar(select(OperationEvidenceEvent).where(OperationEvidenceEvent.session_id==sid).limit(1))
    row.content = {**row.content, 'at':'changed'}; db_session.commit()
    result = finish(client, prepared)
    assert result['status']=='needs_review' and result['suggested_score'] is None
    other = auth_headers(client,'assessment_other','teacher')
    for path in [f'{ROOT}/attempts/{sid}',f'{ROOT}/attempts/{sid}/evidence']:
        assert client.get(path,headers=other).status_code == 404
    assert client.post(f'{ROOT}/attempts/{sid}/evaluate',headers=prepared[0]['student']).status_code==403


def test_ai_commentary_cannot_change_score_and_uses_only_reviewed_summary(client, prepared, clock, monkeypatch):
    roles,_,attempt=prepared
    route(client,prepared); wait(client,prepared,clock,3)
    result=finish(client,prepared); sid=attempt['session_id']
    saved=client.put(f'{ROOT}/attempts/{sid}/grade',headers=roles['teacher'],json={'revision':0,'score':100}).json()
    response=client.post(f'{ROOT}/attempts/{sid}/assessment-review',headers=roles['teacher'],json={
        'evaluation_id':result['id'],'grade_revision':saved['revision']})
    assert response.status_code==200,response.text
    from app.services.operation_assessment import commentary
    monkeypatch.setattr(commentary.settings,'deepseek_api_key','isolated-fake-key')
    calls=[]
    def provider(payload):
        calls.append(payload)
        assert not any(k in json.dumps(payload) for k in ['student_id','standard_log','session_id','event_id','api_key'])
        return '你已正确完成指定接车进路，操作过程中未发现已确认的错误。'
    monkeypatch.setattr(commentary,'provider',provider)
    response=client.post(f'{ROOT}/attempts/{sid}/student-commentary',headers=roles['teacher'],json={'revision':saved['revision']})
    assert response.status_code==200,response.text
    assert response.json()['status']=='ready'
    assert len(calls)==1
    detail=client.get(f'{ROOT}/attempts/{sid}',headers=roles['teacher']).json()
    assert detail['automatic_evaluation']['suggested_score']==100 and detail['grade']['score']==100
    assert client.post(f'{ROOT}/attempts/{sid}/student-commentary',headers=roles['student'],json={'revision':1}).status_code==403


@pytest.mark.parametrize('prepared',[{'wrong_signal_cap':True}],indirect=True)
def test_frozen_critical_cap(client,prepared,clock):
    route(client,prepared,'S5LA');wait(client,prepared,clock,3)
    send(client,prepared,'function',button_id='CANCEL_ROUTE')
    send(client,prepared,'target',target_id='XD',target_kind='signal')
    wait(client,prepared,clock,1)
    route(client,prepared);wait(client,prepared,clock,3)
    evaluation=finish(client,prepared)
    assert evaluation['raw_score']==80 and evaluation['suggested_score']==59


@pytest.mark.parametrize('kind,repeats,expected',[('clear',3,94),('reject',3,90),('wrong',2,80),('target_cancel',1,98),('legitimate_clear',1,100)])
def test_multiple_attempts_caps_and_legal_preparation(client,prepared,clock,kind,repeats,expected):
    for _ in range(repeats):
        if kind in {'clear','legitimate_clear'}:
            send(client,prepared,button_id='D3DA' if kind=='clear' else 'XDLA')
            send(client,prepared,'function',button_id='CLEAR_SELECTION')
        elif kind=='reject':
            send(client,prepared,button_id='XDLA');send(client,prepared,button_id='D3DA')
        else:
            route(client,prepared,'S5LA' if kind=='wrong' else 'SIIILA')
            if kind=='target_cancel':wait(client,prepared,clock,3)
            send(client,prepared,'function',button_id='CANCEL_ROUTE')
            send(client,prepared,'target',target_id='XD',target_kind='signal')
            wait(client,prepared,clock,4)
    route(client,prepared);wait(client,prepared,clock,3)
    result=finish(client,prepared)
    assert result['suggested_score']==expected,result


def test_events_after_cutoff_do_not_gain_signal_points(client,prepared,clock):
    from datetime import datetime
    roles,_,attempt=prepared
    deadline=exams.utc(datetime.fromisoformat(attempt['deadline']))
    clock[0]=deadline-timedelta(seconds=.3)
    route(client,prepared)
    clock[0]=deadline+timedelta(seconds=5)
    result=client.get(f"{ROOT}/attempts/{attempt['session_id']}",headers=roles['teacher']).json()['automatic_evaluation']
    assert result['milestones']=={'A1':True,'A2':True,'A3':False,'A4':False}
    assert result['suggested_score']==59


def test_review_adjustment_publication_and_archive_round_trip(client,prepared,clock,monkeypatch,tmp_path):
    from app.services.operation_assessment import archive
    monkeypatch.setattr(archive,'ROOT',tmp_path)
    roles,_,attempt=prepared
    route(client,prepared);wait(client,prepared,clock,3)
    evaluation=finish(client,prepared);sid=attempt['session_id']
    saved=client.put(f'{ROOT}/attempts/{sid}/grade',headers=roles['teacher'],json={'revision':0,'score':98}).json()
    body={'evaluation_id':evaluation['id'],'grade_revision':saved['revision']}
    assert client.post(f'{ROOT}/attempts/{sid}/assessment-review',headers=roles['teacher'],json=body).status_code==422
    assert client.post(f'{ROOT}/attempts/{sid}/assessment-review',headers=roles['teacher'],json={**body,'reason':'教师核对后的人工调整'}).status_code==200
    published=client.post(f'{ROOT}/attempts/{sid}/grade/publish',headers=roles['teacher'],json={'revision':saved['revision'],'score':98,'comment':'已核对'}).json()
    public=client.get(f'{ROOT}/attempts/{sid}',headers=roles['student']).json()['grade']
    assert public['assessment']['teacher_adjusted'] is True
    assert 'evidence' not in json.dumps(public) and 'evaluation_id' not in json.dumps(public)
    response=client.post(f'{ROOT}/attempts/{sid}/archive',headers=roles['teacher'])
    assert response.status_code==200,response.text
    assert response.json()['verified'] is True
    assert client.post(f'{ROOT}/attempts/{sid}/archive',headers=roles['student']).status_code==403


def test_reevaluation_detects_changed_evidence_without_overwriting_old_version(client,prepared,clock,db_session):
    route(client,prepared);wait(client,prepared,clock,3)
    first=finish(client,prepared);sid=prepared[2]['session_id']
    row=db_session.scalar(select(OperationEvidenceEvent).where(OperationEvidenceEvent.session_id==sid).limit(1))
    row.content={**row.content,'at':'changed-after-grading'};db_session.commit()
    response=client.post(f'{ROOT}/attempts/{sid}/evaluate',headers=prepared[0]['teacher'])
    assert response.status_code==200,response.text
    assert response.json()['status']=='needs_review' and response.json()['version']==first['version']+1
    assert db_session.get(ExamEvaluation,first['id']).content['suggested_score']==100


def test_additive_upgrade_backs_up_existing_rows_and_is_idempotent(tmp_path,monkeypatch):
    import sqlite3
    from sqlalchemy import create_engine, text
    from app.services.operation_assessment import upgrade
    monkeypatch.setattr(upgrade,'ROOT',tmp_path)
    engine=create_engine('sqlite:///'+(tmp_path/'legacy.db').as_posix())
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE retained_marker (id INTEGER PRIMARY KEY, value TEXT)'))
        connection.execute(text("INSERT INTO retained_marker VALUES (1,'retained')"))
    result=upgrade.upgrade(engine)
    assert result['changed'] and result['backup']
    with sqlite3.connect(result['backup']) as copy:
        assert copy.execute('select value from retained_marker').fetchone()[0]=='retained'
    with engine.connect() as connection:
        assert connection.execute(text('select value from retained_marker')).scalar()=='retained'
    assert upgrade.upgrade(engine)=={'changed':False}
    engine.dispose()


def test_device_change_and_its_normal_recovery_are_one_error(client,prepared,clock):
    send(client,prepared,'function',button_id='SWITCH_SINGLE_LOCK')
    send(client,prepared,'target',target_id='7',target_kind='switch')
    send(client,prepared,'function',button_id='SWITCH_SINGLE_UNLOCK')
    send(client,prepared,'target',target_id='7',target_kind='switch')
    route(client,prepared);wait(client,prepared,clock,3)
    result=finish(client,prepared)
    assert result['suggested_score']==95,result
    assert len(result['episodes'])==1 and result['episodes'][0]['recovered'] is True


def test_invalid_training_pin_is_not_a_scored_business_violation(client,prepared,clock):
    route(client,prepared);wait(client,prepared,clock,3)
    send(client,prepared,'function',button_id='MANUAL_UNLOCK_ROUTE')
    send(client,prepared,'target',target_id='XD',target_kind='signal',pin='fake-invalid-pin')
    assert finish(client,prepared)['suggested_score']==100


@pytest.mark.parametrize('behavior',['failure','stale'])
def test_ai_failure_and_stale_response_never_overwrite_grades(client,prepared,clock,monkeypatch,behavior):
    roles,_,attempt=prepared
    route(client,prepared);wait(client,prepared,clock,3)
    evaluation=finish(client,prepared);sid=attempt['session_id']
    saved=client.put(f'{ROOT}/attempts/{sid}/grade',headers=roles['teacher'],json={'revision':0,'score':100}).json()
    assert client.post(f'{ROOT}/attempts/{sid}/assessment-review',headers=roles['teacher'],json={
        'evaluation_id':evaluation['id'],'grade_revision':saved['revision']}).status_code==200
    from app.services.operation_assessment import commentary
    monkeypatch.setattr(commentary.settings,'deepseek_api_key','fake-ai-key')
    def provider(payload):
        if behavior=='failure':raise RuntimeError('provider exception with fake-ai-key')
        assert client.put(f'{ROOT}/attempts/{sid}/grade',headers=roles['teacher'],json={
            'revision':saved['revision'],'score':92,'comment':'教师新修改'}).status_code==200
        return '不应覆盖新成绩的旧评语'
    monkeypatch.setattr(commentary,'provider',provider)
    response=client.post(f'{ROOT}/attempts/{sid}/student-commentary',headers=roles['teacher'],json={'revision':saved['revision']})
    assert response.status_code==200 and response.json()['text'] is None
    detail=client.get(f'{ROOT}/attempts/{sid}',headers=roles['teacher']).json()
    assert detail['grade']['score']==(92 if behavior=='stale' else 100)
    assert detail['automatic_evaluation']['suggested_score']==100
    assert 'fake-ai-key' not in response.text
