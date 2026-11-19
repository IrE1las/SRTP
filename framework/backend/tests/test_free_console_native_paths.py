"""User-observed native regressions: protection is not the vehicle path."""
import pytest

from tests.test_free_console_behaviour import Rig
from app.services.simulation_console.console_station import console_station_package
from app.services.simulation_console.reference_station import reference_station_package


@pytest.mark.parametrize('name,protected,point', [('D3>D11','3DG','3'), ('D11>S5','25DG','25'), ('D1>D7','5DG','5')])
def test_clearance_check_keeps_unused_dg_dark_and_out_of_the_train_path(name, protected, point):
    rig=Rig()
    iid=rig.open(name)
    snap=rig.advance(1)
    assert not snap['sections'][protected]['occupied']
    assert not snap['sections'][protected]['display_locked']
    assert snap['switches'][point]['branch_displays']==['idle']*3
    assert protected not in rig.session.routes[iid]['sections']
    rig=Rig()
    rig.command('SET_SECTION_OCCUPANCY',protected,{'kind':'vehicle'})
    assert not rig.route(name)['accepted']  # clearance guard is still required


def test_reverse_pair_colors_only_the_proved_branches_every_two_seconds():
    rig=Rig();iid=rig.open('D3>D11')
    snap=rig.advance(0)
    assert snap['switches']['5']['branch_displays']==['locked','idle','locked']
    assert snap['switches']['7']['branch_displays']==['locked','idle','locked']
    assert rig.command('SIMULATE_TRAIN_START','5DG',{'route_instance_id':iid})['accepted']
    snap=rig.advance(1.99)
    assert not snap['sections']['IAG']['occupied']
    rig.advance(.02)  # approach
    snap=rig.advance(2)
    assert snap['sections']['5DG']['occupied']
    assert snap['switches']['5']['branch_displays']==['occupied','idle','occupied']
    assert snap['switches']['7']['branch_displays']==['locked','idle','locked']
    assert snap['signals']['D3']['aspect'] is None  # approach has cleared
    snap=rig.advance(2)
    assert not snap['sections']['5DG']['occupied']
    assert snap['sections']['7DG']['occupied']
    assert snap['switches']['7']['branch_displays']==['occupied','idle','occupied']
    assert snap['signals']['D3']['aspect'] is None
    assert snap['switches']['3']['branch_displays']==['idle']*3
    rig.advance(2)
    snap=rig.advance(3.1)
    assert snap['routes'][0]['status']=='released'
    assert not snap['routes'][0]['auto_running']


def test_insulation_separates_13_then_11_without_occupying_lower_points():
    rig=Rig();iid=rig.open('D11>S5')
    rig.command('SIMULATE_TRAIN_START','11DG',{'route_instance_id':iid})
    rig.advance(2)  # approach
    snap=rig.advance(2)
    assert snap['sections']['13DG']['occupied']
    assert not snap['sections']['11DG']['occupied']
    assert snap['switches']['13']['branch_displays']==['occupied','occupied','idle']
    assert snap['switches']['11']['branch_displays']==['locked','locked','idle']
    snap=rig.advance(2)
    assert snap['sections']['11DG']['occupied']
    assert not snap['sections']['13DG']['occupied']
    assert snap['switches']['11']['branch_displays']==['occupied','occupied','idle']
    for sid in ('9','15','25'):
        assert not snap['sections'][sid+'DG']['occupied']
        assert snap['switches'][sid]['branch_displays']==['idle']*3


@pytest.mark.parametrize('name,protected,point', [('D3>D11','3DG','1'),('D1>D7','5DG','5'),('D11>S5','25DG','25')])
def test_clearance_occupancy_is_waived_only_by_the_original_reverse_condition(name,protected,point):
    rig=Rig()
    assert rig.command('SWITCH_TOTAL_REVERSE',point)['accepted']
    rig.advance(2.1)
    rig.command('SET_SECTION_OCCUPANCY',protected,{'kind':'vehicle'})
    result=rig.route(name)
    assert result['accepted'],result['message']


def test_c25_clearance_respects_original_23_25_reverse_condition():
    rig=Rig()
    rig.command('SET_SECTION_OCCUPANCY','21DG',{'kind':'vehicle'})
    result=rig.route('D13>SIII')
    assert result['accepted'],result['message']
    rig.advance(2.1)
    snap=rig.advance(.7)
    assert snap['signals']['D13']['aspect']=='B'
    assert snap['sections']['21DG']['occupied']  # actual input is never erased
    assert '21DG' not in rig.session.routes[snap['routes'][0]['id']]['sections']


@pytest.mark.parametrize('first,second', [('D3>D11','D1>D7'),('D11>S5','D13>SIII')])
def test_parallel_route_can_relieve_an_existing_clearance_reservation(first,second):
    rig=Rig();a=rig.open(first);b=rig.open(second)
    snap=rig.advance(3)
    assert snap['signals'][rig.session.routes[a]['signal']]['aspect']=='B'
    assert snap['signals'][rig.session.routes[b]['signal']]['aspect']=='B'
    assert not any(s['occupied'] for s in snap['sections'].values())


def test_auto_train_stops_at_external_fault_without_clearing_it():
    rig=Rig();iid=rig.open('D12>XI')
    rig.command('SIMULATE_TRAIN_START','16DG',{'route_instance_id':iid})
    rig.advance(4)
    rig.command('SET_SECTION_OCCUPANCY','IG',{'kind':'fault'})
    snap=rig.advance(2)
    assert not snap['routes'][0]['auto_running']
    assert snap['sections']['IG']['occupancy_kind']=='fault'
    assert snap['sections']['16DG']['occupied']


@pytest.mark.parametrize('name', [r['name'] for r in console_station_package()['routes']
                                 if r['kind']=='train' and any(b in ('D7DA','D9DA','D11DA') for b in r['button_sequence'][1:-1])])
def test_train_alternatives_accept_intermediate_shunt_button(name):
    rig=Rig();iid=rig.open(name)
    assert rig.service.routes[rig.session.routes[iid]['route_id']]['kind']=='train'
    old=next(r for r in reference_station_package()['routes'] if r['name']==name)
    assert any(b in ('D7LA','D9LA','D11LA') for b in old['button_sequence'])


def test_filament_break_closes_signal_retains_locks_and_restore_requires_reopen():
    rig=Rig();iid=rig.open('D12>XI')
    snap=rig.command('SIGNAL_FILAMENT_BREAK','D12')['snapshot']
    assert not snap['signals']['D12']['filament_ok']
    assert snap['signals']['D12']['aspect'] is None
    assert snap['sections']['16DG']['locked']
    assert not rig.command('REPEAT_OPEN_SIGNAL',iid)['accepted']
    snap=rig.command('SIGNAL_FILAMENT_RESTORE','D12')['snapshot']
    assert snap['signals']['D12']['filament_ok']
    assert snap['signals']['D12']['aspect'] is None
    assert rig.command('REPEAT_OPEN_SIGNAL',iid)['accepted']


def test_route_guide_checks_position_but_tolerates_track_fault_and_shows_red_white():
    rig=Rig()
    rig.command('SET_SECTION_OCCUPANCY','IG',{'kind':'fault'})
    assert rig.command('GUIDE_ARM','X')['accepted']
    assert rig.session.selected==[]  # no terminal selection for guide
    rig.advance(.7)
    snap=rig.advance(.7)
    assert snap['signals']['X']['aspect']=='HB'
    assert rig.command('GUIDE_MAINTAIN','X')['accepted']
    assert rig.advance(15.01)['signals']['X']['aspect']=='HB'  # first inner DG is clear


def test_total_guide_locks_throat_opens_without_terminal_and_manual_close_keeps_total_lock():
    rig=Rig()
    rig.command('SET_SWITCH_INDICATION','5')
    assert rig.command('GUIDE_TOTAL_LOCK','X')['accepted']
    assert rig.command('SWITCH_TOTAL_REVERSE','1')['reason_code']=='GUIDE_TOTAL_LOCKED'
    snap=rig.command('GUIDE_ARM','X')['snapshot']
    assert snap['signals']['X']['aspect']=='HB'
    assert snap['selected_buttons']==[]
    assert len(snap['routes'])==1
    assert snap['routes'][0]['mode']=='guide_total'
    assert snap['routes'][0]['sections'][-1]=='IG'
    assert rig.command('GUIDE_TOTAL_UNLOCK','X')['reason_code']=='GUIDE_SIGNAL_OPEN'
    rig.advance(10)
    assert rig.command('GUIDE_MAINTAIN','X')['accepted']
    assert rig.advance(10)['signals']['X']['aspect']=='HB'
    snap=rig.command('MANUAL_UNLOCK_ROUTE','X')['snapshot']
    assert snap['signals']['X']['aspect'] is None
    assert snap['guide_locks']==['X']
    assert rig.command('GUIDE_TOTAL_UNLOCK','X')['accepted']


def test_total_guide_closes_on_entry_and_does_not_release_throat_lock():
    rig=Rig()
    rig.command('GUIDE_TOTAL_LOCK','X');rig.command('GUIDE_ARM','X')
    assert rig.command('GUIDE_ARM','XF')['reason_code']=='GUIDE_THROAT_BUSY'
    rig.command('SET_SECTION_OCCUPANCY','IAG',{'kind':'vehicle'})
    snap=rig.advance(.1)
    assert snap['signals']['X']['aspect'] is None
    assert snap['guide_locks']==['X']
    assert rig.command('GUIDE_TOTAL_UNLOCK','X')['reason_code']=='THROAT_OCCUPIED'


def test_train_and_guide_signals_close_on_first_inner_dg():
    for guide in (False, True):
        rig=Rig()
        if guide:
            rig.command('GUIDE_ARM','X')
            rig.advance(.7)
            iid=next(iter(rig.session.routes))
        else:
            iid=rig.open('L_X>SI')
        assert rig.session.signals['X']['aspect']==('HB' if guide else 'U')
        rig.command('SIMULATE_TRAIN_START','5DG',{'route_instance_id':iid})
        assert rig.advance(2)['signals']['X']['aspect']==('HB' if guide else 'U')
        assert rig.advance(2)['signals']['X']['aspect'] is None


def test_iag_normal_signal_close_is_a_train_event_and_movement_continues():
    rig=Rig();iid=rig.open('L_X>SI')
    assert rig.command('SIMULATE_TRAIN_START','IAG',{'route_instance_id':iid})['accepted']
    rig.advance(2)
    snap=rig.advance(2)
    assert snap['sections']['IAG']['occupied']
    assert snap['signals']['X']['aspect'] is None
    assert snap['routes'][0]['auto_running']
    assert any(e['kind']=='train_signal_close' and e['route_id']==rig.session.routes[iid]['route_id'] for e in snap['events'])
    assert not any(e['kind'] in ('signal_close','rejected') for e in snap['events'])
    snap=rig.advance(2)
    assert snap['sections']['5DG']['occupied']


def test_loss_of_indication_still_records_an_abnormal_signal_close():
    rig=Rig();rig.open('L_X>SI')
    assert not rig.command('SET_SWITCH_INDICATION','5')['accepted']
    rig.session.switches['5'].update(represented=False, indication_fault=True)
    with rig.clock():
        rig.service._protect_point_signals(rig.session)
    snap=rig.advance(0)
    assert snap['signals']['X']['aspect'] is None
    assert any(e['kind']=='signal_close' for e in snap['events'])


@pytest.mark.parametrize('entry', ['X','S'])
def test_total_guide_indication_covers_only_its_throat_and_preserves_manual_locks(entry):
    rig=Rig()
    throat=rig.service._entry(entry)['throat']
    points={p['id'] for p in rig.service.package['switches'] if p['throat']==throat}
    own=sorted(points,key=int)[0]
    assert rig.command('SWITCH_SINGLE_LOCK',own)['accepted']
    manual={sid:s['manual_locked'] for sid,s in rig.session.switches.items()}
    snap=rig.command('GUIDE_TOTAL_LOCK',entry)['snapshot']
    assert {sid for sid,p in snap['switches'].items() if p['guide_total_locked']}==points
    assert {sid:p['manual_locked'] for sid,p in snap['switches'].items()}==manual
    for sid in points:
        assert rig.command('SWITCH_TOTAL_REVERSE',sid)['reason_code']=='GUIDE_TOTAL_LOCKED'
    snap=rig.command('GUIDE_TOTAL_UNLOCK',entry)['snapshot']
    assert not any(p['guide_total_locked'] for p in snap['switches'].values())
    assert {sid:p['manual_locked'] for sid,p in snap['switches'].items()}==manual


def test_every_original_row_finishes_automatic_movement_on_its_insulated_sections():
    for route in console_station_package()['routes']:
        rig=Rig()
        with rig.clock():
            result=rig.service._arrange(rig.session,route)
        assert result['accepted'],(route['id'],result['message'])
        iid=result['snapshot']['routes'][0]['id']
        rig.advance(2.1);rig.advance(.7)
        result=rig.command('SIMULATE_TRAIN_START',route['sections'][0],{'route_instance_id':iid})
        assert result['accepted'],(route['id'],result['message'])
        snap=rig.advance((len(route['movement_groups'])+3)*2+3.1)
        assert snap['routes'][0]['status']=='released',route['id']
        assert not any(s['occupied'] or s['locked'] for s in snap['sections'].values()),route['id']


@pytest.mark.parametrize('name,first,second', [
    ('D11>S5','13DG','11DG'),('S5>XD','11DG','13DG'),
    ('D1>D7','1DG','3DG'),('D7>D1','3DG','1DG'),
    ('D3>D11','5DG','7DG'),('S5>D3','7DG','5DG'),
    ('D9>S5','9DG','11DG'),('S5>D9','11DG','9DG'),
    ('D11>D13','13DG','15DG'),('SI>XD','15DG','13DG'),
    ('D13>SII','17DG','19DG'),('SII>D9','19DG','17DG'),
    ('D13>SIII','23DG','25DG'),('SIII>D9','25DG','23DG'),
    ('D2>XI','2DG','4DG'),('D10>D2','4DG','2DG'),
    ('D10>D6','8DG','6DG'),('D6>XI','6DG','8DG'),
    ('D8>XII','10DG','12DG'),('L_XII>SF','12DG','10DG'),
    ('D18>D12','20DG','18DG'),('D12>D16','18DG','20DG'),
])
def test_pair_steps_follow_connected_branches_and_route_direction(name,first,second):
    rig=Rig();iid=rig.open(name)
    route=rig.service.routes[rig.session.routes[iid]['route_id']]
    assert route['sections'].index(second)==route['sections'].index(first)+1
    assert all(len(group)==1 for group in route['movement_groups'])
    rig.command('SIMULATE_TRAIN_START',route['sections'][0],{'route_instance_id':iid})
    for _ in range(len(route['sections'])+2):
        rig.advance(2)
        if rig.session.sections[first]['occupied']:
            break
    assert rig.session.sections[first]['occupied']
    assert not rig.session.sections[second]['occupied']
    snap=rig.advance(2)
    assert snap['sections'][second]['occupied']
    assert not snap['sections'][first]['occupied']


def test_reverse_crossover_flank_ends_are_demands_but_not_vehicle_steps():
    p=console_station_package()
    route=next(r for r in p['routes'] if r['name']=='D9>S5')
    assert route['sections']==['9DG','11DG','21DG','5G']
    assert '13' in route['switches'] and '15' in route['switches']
    assert '13' not in route['path_switches'] and '15' not in route['path_switches']


def test_non_point_and_approach_targets_start_their_corresponding_train():
    for route in console_station_package()['routes']:
        candidates=[n for n in route['sections'] if not next(s for s in console_station_package()['sections'] if s['name']==n)['switches']]
        approach=route['approach_section']
        if approach and approach not in route['sections']:
            candidates.append(approach)
        for target in candidates:
            rig=Rig()
            with rig.clock():
                result=rig.service._arrange(rig.session,route)
            assert result['accepted']
            iid=result['snapshot']['routes'][0]['id']
            rig.advance(2.1);rig.advance(.7)
            result=rig.command('SIMULATE_TRAIN_START',target,{'route_instance_id':iid})
            assert result['accepted'],(route['id'],target,result['message'])
            assert result['snapshot']['routes'][0]['auto_running']
