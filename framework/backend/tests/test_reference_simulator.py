"""Regression checks for recovered geometry and operator commands."""
import importlib.util
import json
from pathlib import Path
import struct

import pytest

from app.services.simulation_console import runtime, console_commands
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.reference_runtime import ReferenceSimulationService
from app.services.simulation_console.commands import dump_session, load_session


def service():
    return ReferenceSimulationService(reference_station_package())


def press(svc, snapshot, buttons):
    for button in buttons:
        response = svc.select_button(snapshot['session_id'], 17, button, snapshot['version'])
        snapshot = response['snapshot']
    return response


def command(svc, snap, kind, target, **extra):
    return console_commands.operate(svc, snap['session_id'], 17, {'type':kind, 'target':target, **extra}, snap['version'])


def test_native_geometry_is_complete_and_not_a_screenshot_overlay():
    data = json.loads(Path(runtime.__file__).with_name('reference_data.json').read_text('utf-8'))
    assert data['geometry']['bytes_consumed'] == 10656
    assert {b['type']:b['count'] for b in data['geometry']['blocks']} == {0:17,1:15,2:25,3:12,4:5,501:58,502:9}
    records = data['geometry']['records']
    sw = next(r for r in records if r.get('name')=='25' and r['type']==2)
    assert sw['point'] == [580,280]
    assert sw['branches'] == [[[620,280]],[[520,280]],[[540,320]]]
    package = reference_station_package()
    assert package['counts']['ready_routes'] == 199
    assert package['counts']['blocked_routes'] == 0
    assert set(s['name'] for s in package['sections']) == set(r['section'] for r in records if r['type']==2) | set(r['name'] for r in records if r['type'] in {3,4})


def test_binary_parser_rejects_bad_record_and_truncated_input():
    path = Path(__file__).parents[3]/'tools'/'reference_simulator'/'import_station.py'
    spec=importlib.util.spec_from_file_location('sdm_import',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError,match='Unrecognized block'):
        module.decode_geometry(struct.pack('<ii',999,1))
    with pytest.raises(ValueError,match='Truncated'):
        module.decode_geometry(struct.pack('<ii',2,1))


def test_every_enabled_native_route_can_arrange_drive_and_release(monkeypatch):
    clock=[1000.]
    monkeypatch.setattr(runtime,'monotonic',lambda:clock[0])
    svc=service()
    for route in svc.package['routes']:
        if route['status']!='ready':
            continue
        snapshot=svc.new_session(17)
        response=press(svc,snapshot,route['button_sequence'])
        assert response['accepted'],(route['name'],response['message'])
        snapshot=response['snapshot']
        instance=snapshot['routes'][0]
        for _ in range(len(instance['sections'])+1+int(instance['progress']==-2)):
            response=svc.step_train(snapshot['session_id'],17,instance['id'],snapshot['version'])
            assert response['accepted'],(route['name'],response['message'])
            snapshot=response['snapshot']
        clock[0]+=3.1
        snapshot=svc.snapshot(snapshot['session_id'],17)
        assert snapshot['routes'][0]['status']=='released',route['name']
        assert not any(state['locked'] for state in snapshot['sections'].values())
        assert not any(state['locked'] for state in snapshot['switches'].values())


def test_native_route_previously_blocked_by_unrelated_workbook_can_open():
    svc=service()
    route=next(r for r in svc.package['routes'] if r['name']=='D9>S5')
    assert route['status']=='ready'
    result=press(svc,svc.new_session(17),route['button_sequence'])
    assert result['accepted']
    assert result['snapshot']['signals']['D9']['aspect']=='B'
    assert route['switches']['13']==route['switches']['15']==0


def test_pair_switch_lock_seal_and_occupancy_guards():
    svc=service();snap=svc.new_session(17)
    result=command(svc,snap,'SWITCH_TOTAL_REVERSE','1')
    assert result['accepted']
    assert result['snapshot']['switches']['1']['position']==result['snapshot']['switches']['3']['position']==1
    result=command(svc,result['snapshot'],'SWITCH_SINGLE_LOCK','1')
    result=command(svc,result['snapshot'],'SWITCH_TOTAL_NORMAL','3')
    assert not result['accepted'] and result['reason_code']=='SWITCH_MANUAL_LOCKED'
    snap=svc.new_session(17)
    result=command(svc,snap,'SET_SECTION_OCCUPANCY','1DG',payload={'kind':'fault'})
    result=command(svc,result['snapshot'],'SWITCH_TOTAL_REVERSE','1')
    assert not result['accepted'] and result['reason_code']=='SECTION_OCCUPIED'


def test_pin_sealing_and_lamp_state_survive_normal_close():
    svc=service();snap=svc.new_session(17)
    result=command(svc,snap,'SIGNAL_SEAL','D3',pin='wrong')
    assert not result['accepted'] and result['reason_code']=='INVALID_PIN'
    result=command(svc,result['snapshot'],'SIGNAL_SEAL','D3',pin='0000')
    result=press(svc,result['snapshot'],['D3DA'])
    assert not result['accepted'] and result['reason_code']=='SIGNAL_BUTTON_SEALED'
    result=command(svc,result['snapshot'],'SIGNAL_UNSEAL','D3',pin='0000')
    result=press(svc,result['snapshot'],['D3DA','D7DA'])
    assert result['accepted']
    instance=result['snapshot']['routes'][0]['id']
    result=command(svc,result['snapshot'],'SIGNAL_SEAL','D3',pin='0000')
    result=command(svc,result['snapshot'],'CANCEL_ROUTE',instance)
    assert result['accepted'] and result['snapshot']['signals']['D3']['sealed']


def test_manual_unlock_closes_first_and_holds_locks_until_native_delay(monkeypatch):
    clock=[1000.]
    monkeypatch.setattr(runtime,'monotonic',lambda:clock[0])
    monkeypatch.setattr(console_commands,'monotonic',lambda:clock[0])
    svc=service()
    result=press(svc,svc.new_session(17),['D3DA','D7DA'])
    snap=result['snapshot'];instance=snap['routes'][0]
    result=command(svc,snap,'MANUAL_UNLOCK_ROUTE',instance['id'],pin='0000')
    assert result['accepted']
    snap=result['snapshot']
    assert snap['signals']['D3']['aspect'] is None
    assert snap['routes'][0]['manual_remaining_seconds']==30
    assert any(state['locked'] for state in snap['switches'].values())
    rejected=command(svc,snap,'CANCEL_ROUTE',instance['id'])
    assert not rejected['accepted'] and rejected['reason_code']=='UNLOCK_PENDING'
    clock[0]+=29
    assert svc.snapshot(snap['session_id'],17)['routes'][0]['status']=='manual_unlocking'
    # Occupancy at the expiry must prevent release, even after the timer expires.
    session=svc._get(snap['session_id'],17)
    section=instance['sections'][0];session.sections[section]['occupied']=True
    clock[0]+=2
    assert svc.snapshot(snap['session_id'],17)['routes'][0]['status']=='manual_unlocking'
    session.sections[section]['occupied']=False
    snap=svc.snapshot(snap['session_id'],17)
    assert snap['routes'][0]['status']=='released'
    assert not any(state['locked'] for state in snap['switches'].values())


def test_commands_reject_stale_version_and_cross_owner():
    svc=service();snap=svc.new_session(17)
    command(svc,snap,'SWITCH_SINGLE_LOCK','1')
    with pytest.raises(runtime.SimulationError,match='版本'):
        command(svc,snap,'SWITCH_SINGLE_UNLOCK','1')
    with pytest.raises(runtime.SimulationError,match='无权'):
        console_commands.operate(svc,snap['session_id'],18,{'type':'SWITCH_SINGLE_UNLOCK','target':'1'},None)


def test_manual_unlock_deadline_roundtrips_through_durable_session():
    svc=service();result=press(svc,svc.new_session(17),['D3DA','D7DA'])
    result=command(svc,result['snapshot'],'MANUAL_UNLOCK_ROUTE',result['snapshot']['routes'][0]['id'],pin='0000')
    original=svc._get(result['snapshot']['session_id'],17)
    saved=load_session(dump_session(original))
    assert next(iter(saved.routes.values()))['manual_release_due']==pytest.approx(next(iter(original.routes.values()))['manual_release_due'],abs=0.1)


def test_reference_http_selection_ownership_and_fault_permissions(client,db_session):
    from app.models.user import User
    from app.core.security import create_access_token
    from app.api.simulation_console import reference_service
    people=[]
    for name,role in [('reference_student','student'),('reference_other','student'),('reference_teacher','teacher')]:
        user=User(username=name,password_hash='test-only',real_name=name,role=role)
        db_session.add(user);people.append(user)
    db_session.commit()
    auth=[{'Authorization':f"Bearer {create_access_token({'sub':str(u.id)})}"} for u in people]
    student,other,teacher=auth
    root='/api/simulation-console'
    package=client.get(root+'/station?source=reference',headers=student).json()
    assert package['profile']=='reference' and 'routes' not in package and 'source' not in package
    assert package['counts']['sections']==35
    assert client.get(root+'/station?source=reference',headers=teacher).json()['routes']
    snap=client.post(root+'/sessions',headers=student,json={'source':'reference'}).json()
    assert snap['profile']=='reference'
    url=root+'/sessions/'+snap['session_id']
    assert client.get(url,headers=other).status_code==409
    forbidden={'type':'SET_SECTION_OCCUPANCY','target':'IAG','payload':{'kind':'fault'},'version':snap['version']}
    assert client.post(url+'/commands',headers=student,json=forbidden).status_code==403
    for button in ['D3DA','D7DA']:
        reply=client.post(url+'/buttons',headers=student,json={'button':button,'version':snap['version']})
        assert reply.status_code==200 and reply.json()['accepted']
        snap=reply.json()['snapshot']
    assert snap['signals']['D3']['aspect']=='B'
    assert client.post(url+'/advance',headers=student,json={'route_instance_id':snap['routes'][0]['id'],'version':snap['version']}).status_code==403
    assert client.post(url+'/commands',headers=student,json={'type':'SIGNAL_UNSEAL','target':'D3','pin':'wrong','version':snap['version']}).json()['reason_code']=='INVALID_PIN'
    reference_service.sessions.pop(snap['session_id'],None)
