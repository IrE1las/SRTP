"""Original station fixtures, module isolation and degraded-mode scenarios."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.services.simulation_console import runtime, console_commands, station
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.reference_runtime import ReferenceSimulationService
from app.services.simulation_console import reference_runtime


@pytest.fixture(autouse=True)
def native_clock_follows_runtime(monkeypatch):
    monkeypatch.setattr(reference_runtime, 'monotonic', lambda: runtime.monotonic())


def service():
    return ReferenceSimulationService(reference_station_package())


def operate(svc,snap,kind,target,pin=None,**extra):
    return console_commands.operate(svc,snap['session_id'],21,
                                    {'type':kind,'target':target,'pin':pin,**extra},snap['version'])


def press(svc,snap,buttons):
    for button in buttons:
        result=svc.select_button(snap['session_id'],21,button,snap['version'])
        snap=result['snapshot']
    return result


def test_native_compiler_never_consults_teaching_workbook(monkeypatch):
    before=deepcopy(station.station_package())
    monkeypatch.setattr(station,'station_package',lambda:pytest.fail('native compiler read teaching workbook'))
    reference_station_package.cache_clear()
    package=reference_station_package()
    assert len(package['routes'])==199 and all(r['condition_source']=='original_application' for r in package['routes'])
    assert all('checked_route_id' not in r for r in package['routes'])
    svc=service()
    assert press(svc,svc.new_session(21),['D9DA','S5DA'])['accepted']
    assert before['counts']['ready_routes']==193


def test_mixed_case_and_unnamed_native_controls_are_separate():
    data=json.loads(Path(runtime.__file__).with_name('reference_data.json').read_text('utf8'))
    blocks={b['id']:b['fields'] for b in data['topology_blocks']}
    assert blocks['ZXJ_Control_1']=={'StartSignal':'X','EndSignal':'SI','PointNumber':'0x6'}
    assert data['topology']['COPD18']['Name']=='COPD18'
    assert data['topology']['SemiBlock_XD']=={'Name':'SemiBlock_XD','Signal':'XD','Throat':'0x1'}
    assert len(reference_station_package()['blocks'])==5


def test_native_route_sections_and_straight_aspects_use_own_files():
    routes={r['name']:r for r in reference_station_package()['routes']}
    assert routes['D9>S5']['sections']==['9-15DG','11-13DG','21DG','5G']
    assert routes['D6>D10']['sections']==['6-12DG','8-10DG']
    assert routes['L_X>SI']['approach_section']=='YXG'
    assert routes['L_X>SI']['aspect']=='U'
    assert routes['L_X>S5']['aspect']=='UU'
    assert routes['L_XTA>SF']['segment_signals']==['X','XI']
    assert routes['D1>D7']['clearance_checks']==[{'section':'5DG','clear_if_any':{'5':1,'7':1},'source':'C3FCX'}]
    # Native ADD_1 protects the selected C17/C19 crossover with C23 normal;
    # this demand is absent from Route.txt but explicit in STADATA.
    assert routes['D13>SII']['switches']['23']==routes['D13>SII']['switches']['25']==0


@pytest.mark.parametrize('route',reference_station_package()['routes'],ids=lambda r:f"{r['id']}:{r['name']}")
def test_each_original_definition_arranges_runs_and_releases(route,monkeypatch):
    clock=[2000.]
    monkeypatch.setattr(runtime,'monotonic',lambda:clock[0])
    svc=service();snap=svc.new_session(21)
    # Directly select each original definition so same-button alternatives are
    # independently exercised, instead of repeatedly testing the default one.
    session=svc._get(snap['session_id'],21)
    result=svc._arrange(session,route)
    assert result['accepted'],result['message']
    snap=result['snapshot']
    if any(snap['switches'][sid]['moving'] for sid in route['switches']):
        assert snap['routes'][0]['status']=='setting'
        assert all(snap['signals'][name]['aspect'] is None for name in route['segment_signals'])
    clock[0]+=2.1
    snap=svc.snapshot(snap['session_id'],21);instance=snap['routes'][0]
    assert all(snap['switches'][sid]['position']==pos for sid,pos in route['switches'].items())
    assert all(snap['signals'][name]['aspect'] is not None for name in route['segment_signals'])
    for _ in range(len(instance['sections'])+1+int(instance['progress']==-2)):
        result=svc.step_train(snap['session_id'],21,instance['id'],snap['version'])
        assert result['accepted'],result['message']
        snap=result['snapshot']
    clock[0]+=3.1
    snap=svc.snapshot(snap['session_id'],21)
    assert snap['routes'][0]['status']=='released'
    assert not any(s['locked'] for s in snap['switches'].values())
    assert not any(s['locked'] for s in snap['sections'].values())
    assert all(snap['signals'][name]['aspect'] is None for name in route['segment_signals'])


def test_native_clearance_fault_blocks_then_reverse_isolation_allows(monkeypatch):
    clock=[1000.]
    monkeypatch.setattr(runtime,'monotonic',lambda:clock[0])
    svc=service();snap=svc.new_session(21,occupied_sections=['5DG'])
    result=press(svc,snap,['D1DA','D7DA'])
    assert not result['accepted'] and '5DG' in result['devices']
    # Native FCX_1 permits clearance when the protective 5/7 pair is reversed.
    session=svc._get(snap['session_id'],21)
    session.sections['5DG'].update(occupied=False,occupancy_kind='clear')
    result=operate(svc,result['snapshot'],'SWITCH_TOTAL_REVERSE','5')
    clock[0]+=2.1
    result['snapshot']=svc.snapshot(snap['session_id'],21)
    session.sections['5DG'].update(occupied=True,occupancy_kind='vehicle')
    result=press(svc,result['snapshot'],['D1DA','D7DA'])
    assert result['accepted']


def test_same_button_native_alternatives_are_not_data_errors():
    svc=service();snap=svc.new_session(21)
    result=press(svc,snap,['S5DA','D3DA'])
    assert result['accepted']
    assert any(e['kind']=='route_alternative' for e in result['snapshot']['events'])


def test_guide_requires_aligned_points_respects_vehicle_and_expires(monkeypatch):
    clock=[1000.]
    monkeypatch.setattr(runtime,'monotonic',lambda:clock[0])
    import app.services.simulation_console.reference_runtime as native
    monkeypatch.setattr(native,'monotonic',lambda:clock[0])
    svc=service();snap=svc.new_session(21)
    # X -> SI is the all-normal receiving path in original STADATA.
    result=operate(svc,snap,'SET_SECTION_OCCUPANCY','3DG',payload={'kind':'fault'})
    result=press(svc,result['snapshot'],['XLA','SILA'])
    assert not result['accepted']
    result=operate(svc,result['snapshot'],'GUIDE_ARM','X',pin='0000')
    result=press(svc,result['snapshot'],['SILA'])
    assert result['accepted'] and result['snapshot']['signals']['X']['aspect']=='HB'
    clock[0]+=10
    result=operate(svc,svc.snapshot(snap['session_id'],21),'GUIDE_MAINTAIN','X')
    assert result['accepted']
    clock[0]+=16
    snap=svc.snapshot(snap['session_id'],21)
    assert snap['signals']['X']['aspect'] is None and any(s['locked'] for s in snap['sections'].values())
    assert not operate(svc,snap,'REPEAT_OPEN_SIGNAL',snap['routes'][0]['id'])['accepted']
    svc=service();snap=svc.new_session(21,occupied_sections=['3DG'])
    result=operate(svc,snap,'GUIDE_ARM','X',pin='0000')
    assert not press(svc,result['snapshot'],['SILA'])['accepted']


def test_guide_total_lock_is_throat_scoped_and_prevents_switching():
    svc=service();snap=svc.new_session(21)
    result=operate(svc,snap,'GUIDE_TOTAL_LOCK','X',pin='0000')
    assert result['accepted']
    result=operate(svc,result['snapshot'],'SWITCH_TOTAL_REVERSE','1')
    assert result['reason_code']=='GUIDE_TOTAL_LOCKED'
    result=press(svc,result['snapshot'],['D3DA','D7DA'])
    assert result['reason_code']=='GUIDE_TOTAL_LOCKED'
    # The other throat still operates.
    result=press(svc,result['snapshot'],['D2DA','D4DA'])
    assert result['accepted']
    result=operate(svc,result['snapshot'],'GUIDE_TOTAL_UNLOCK','X',pin='0000')
    assert result['accepted'] and not result['snapshot']['guide_locks']


def test_section_fault_unlock_is_single_target_timed_and_never_clears_occupancy(monkeypatch):
    import app.services.simulation_console.reference_runtime as native
    clock=[1000.]
    monkeypatch.setattr(native,'monotonic',lambda:clock[0])
    svc=service();result=press(svc,svc.new_session(21),['D3DA','D7DA'])
    result=operate(svc,result['snapshot'],'SET_SECTION_OCCUPANCY','5DG',payload={'kind':'vehicle'})
    result=operate(svc,result['snapshot'],'SECTION_FAULT_UNLOCK','5DG',pin='0000')
    assert not result['accepted'] and result['snapshot']['sections']['5DG']['occupied']
    result=operate(svc,result['snapshot'],'CLEAR_SECTION_OCCUPANCY','5DG')
    result=operate(svc,result['snapshot'],'SECTION_FAULT_UNLOCK','5DG',pin='0000')
    assert result['accepted'] and result['snapshot']['sections']['5DG']['locked']
    result=operate(svc,result['snapshot'],'CANCEL_ROUTE',result['snapshot']['routes'][0]['id'])
    assert not result['accepted'] and result['reason_code']=='UNLOCK_PENDING'
    clock[0]+=31
    snap=svc.snapshot(result['snapshot']['session_id'],21)
    assert not snap['sections']['5DG']['locked'] and snap['sections']['3DG']['locked']
    assert snap['signals']['D3']['aspect'] is None


def test_block_request_requires_peer_and_does_not_change_another_block():
    svc=service();snap=svc.new_session(21,interval_available=False)
    result=press(svc,snap,['S5LA','XDLA'])
    assert result['reason_code']=='BLOCK_PERMISSION_REQUIRED'
    result=operate(svc,result['snapshot'],'BLOCK_PEER_ACCEPT','XD')
    assert not result['accepted']
    result=operate(svc,result['snapshot'],'BLOCK_REQUEST','XD')
    assert result['accepted'] and not result['snapshot']['blocks']['XD']['permission']
    result=operate(svc,result['snapshot'],'BLOCK_PEER_ACCEPT','XD')
    assert result['accepted'] and not result['snapshot']['blocks']['X']['permission']
    result=press(svc,result['snapshot'],['S5LA','XDLA'])
    assert result['accepted']
    result=operate(svc,result['snapshot'],'BLOCK_ACCIDENT_RESET','XD',pin='0000')
    assert not result['accepted'] and result['snapshot']['blocks']['XD']['permission']


def test_native_operations_leave_original_teaching_package_and_session_unchanged():
    teaching=runtime.SimulationService();snap=teaching.new_session(21)
    package=deepcopy(teaching.package)
    svc=service();result=operate(svc,svc.new_session(21),'GUIDE_TOTAL_LOCK','X',pin='0000')
    result=operate(svc,result['snapshot'],'BLOCK_ACCIDENT_RESET','XD',pin='0000')
    assert teaching.package==package
    assert teaching.snapshot(snap['session_id'],21)==snap
    assert 'blocks' not in snap and 'guide_locks' not in snap


@pytest.mark.parametrize('name,signals', [('D1>S5',['D1','D9']),('L_XTA>SF',['X','XI'])])
def test_composite_cancel_only_releases_selected_basic_segment(name,signals,monkeypatch):
    clock=[1000.]
    monkeypatch.setattr(runtime,'monotonic',lambda:clock[0])
    svc=service();snap=svc.new_session(21)
    definition=next(r for r in svc.package['routes'] if r['name']==name)
    result=press(svc,snap,definition['button_sequence'])
    clock[0]+=2.1
    result['snapshot']=svc.snapshot(snap['session_id'],21)
    snap=result['snapshot'];instance=snap['routes'][0]
    first,second=[svc.routes[cid] for cid in definition['subroutes']]
    result=operate(svc,snap,'CANCEL_ROUTE',instance['id'],payload={'signal':signals[0]})
    assert result['accepted']
    snap=result['snapshot']
    assert snap['signals'][signals[0]]['aspect'] is None
    assert snap['signals'][signals[1]]['aspect'] is not None
    assert all(snap['sections'][n]['locked'] for n in second['sections'])
    result=operate(svc,snap,'CANCEL_ROUTE',instance['id'],payload={'signal':signals[1]})
    assert result['accepted'] and result['snapshot']['routes'][0]['status']=='cancelled'
    assert not any(s['locked'] for s in result['snapshot']['sections'].values())


def test_console_peer_http_permission_and_workbook_rejects_native_commands(client,db_session):
    from app.models.user import User
    from app.core.security import create_access_token
    users=[]
    for name,role in [('native_student','student'),('native_teacher','teacher')]:
        user=User(username=name,password_hash='fixture',role=role)
        db_session.add(user);users.append(user)
    db_session.commit()
    student,teacher=[{'Authorization':f"Bearer {create_access_token({'sub':str(u.id)})}"} for u in users]
    root='/api/simulation-console'
    snap=client.post(root+'/sessions',headers=student,json={'source':'reference','interval_available':False}).json()
    url=root+'/sessions/'+snap['session_id']+'/commands'
    response=client.post(url,headers=student,json={'type':'BLOCK_PEER_ACCEPT','target':'XD','version':snap['version']})
    assert response.status_code==403
    snap=client.post(root+'/sessions',headers=teacher,json={'source':'workbook'}).json()
    response=client.post(root+'/sessions/'+snap['session_id']+'/commands',headers=teacher,
                         json={'type':'GUIDE_TOTAL_LOCK','target':'X','pin':'0000','version':snap['version']})
    assert response.status_code==200 and not response.json()['accepted']
    assert 'guide_locks' not in response.json()['snapshot']
