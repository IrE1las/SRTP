"""Recorded original-application operations, excluding subjective questions.

The names in the document are examples; parameterized checks also exercise
other points, reception signals and the boundaries of the same rules.
"""
import pytest

from tests.test_free_console_behaviour import Rig
from app.services.simulation_console.console_station import console_station_package


def press(rig, *buttons):
    with rig.clock():
        for button in buttons:
            reply=rig.service.select_button(rig.session.id,31,button,rig.session.version)
    return reply


def set_path(rig, name):
    route=name if isinstance(name,dict) else next(r for r in rig.service.package['routes'] if r['name']==name)
    for sid,pos in route['switches'].items():
        assert rig.command('RESTORE_SWITCH_INDICATION',sid,{'position':pos})['accepted']
    return route


def exact_open(rig, route):
    with rig.clock():
        result=rig.service._arrange(rig.session,route)
    assert result['accepted'],result['message']
    rig.advance(2.1);rig.advance(.7)
    return result['snapshot']['routes'][-1]['id']


@pytest.mark.parametrize('point',['1','5','9','13','2','6','10','18'])
def test_seal_inhibits_selection_but_not_individual_movement(point):
    rig=Rig()
    assert rig.command('SWITCH_SEAL',point)['accepted']
    result=rig.command('SWITCH_TOTAL_REVERSE',point)
    assert result['accepted'],result['message']
    assert rig.advance(2.1)['switches'][point]['position']==1
    assert rig.command('SWITCH_SINGLE_LOCK',point)['accepted']
    assert not rig.command('SWITCH_TOTAL_NORMAL',point)['accepted']
    assert rig.command('SWITCH_SINGLE_UNLOCK',point)['accepted']
    assert rig.command('SWITCH_TOTAL_NORMAL',point)['accepted']


@pytest.mark.parametrize('point,occupied',[('5','7DG'),('9','11DG'),('6','8DG'),('18','20DG')])
def test_occupancy_on_either_coupled_end_prevents_pair_movement(point,occupied):
    rig=Rig();rig.command('SET_SECTION_OCCUPANCY',occupied,{'kind':'vehicle'})
    assert rig.command('SWITCH_TOTAL_REVERSE',point)['reason_code']=='SECTION_OCCUPIED'
    assert rig.session.switches[point]['position']==0


@pytest.mark.parametrize('position,allowed',[(0,True),(1,False)])
def test_d1_to_d15_uses_existing_non_point_terminal_and_checks_position(position,allowed):
    rig=Rig()
    if position:
        rig.command('SWITCH_TOTAL_REVERSE','1');rig.advance(2.1)
    rig.command('SWITCH_SINGLE_LOCK','1')
    result=press(rig,'D1DA','D15DA')
    assert result['accepted']==allowed,result['message']


@pytest.mark.parametrize('kind',['vehicle','fault'])
def test_basic_shunt_terminal_occupancy_is_allowed_without_erasing_it(kind):
    rig=Rig();rig.command('SET_SECTION_OCCUPANCY','1/19WG',{'kind':kind})
    result=press(rig,'D1DA','D15DA')
    assert result['accepted'],result['message']
    assert result['snapshot']['sections']['1/19WG']['occupancy_kind']==kind
    rig=Rig();rig.command('SET_SECTION_OCCUPANCY','1DG',{'kind':kind})
    assert not press(rig,'D1DA','D15DA')['accepted']


def test_long_shunt_checks_internal_wg_but_separate_basic_routes_can_be_arranged():
    rig=Rig();rig.command('SET_SECTION_OCCUPANCY','1/19WG',{'kind':'vehicle'})
    assert not rig.route('D1>S4')['accepted']
    rig.open('D15>S4')
    result=press(rig,'D1DA','D15DA')
    assert result['accepted'],result['message']
    snap=rig.advance(.7)
    assert snap['signals']['D15']['aspect']=='B'
    assert snap['signals']['D1']['aspect']=='B'
    assert snap['sections']['1/19WG']['occupied']


def test_later_basic_segment_fault_closes_only_its_signal_and_reopens_only_after_command():
    rig=Rig();iid=rig.open('D1>S4')
    snap=rig.command('SET_SECTION_OCCUPANCY','19DG',{'kind':'fault'})['snapshot']
    assert snap['signals']['D15']['aspect'] is None
    assert snap['signals']['D1']['aspect']=='B'
    assert not rig.command('REPEAT_OPEN_SIGNAL',iid,{'signal':'D15'})['accepted']
    snap=rig.command('CLEAR_SECTION_OCCUPANCY','19DG')['snapshot']
    assert snap['signals']['D15']['aspect'] is None
    assert snap['signals']['D1']['aspect']=='B'
    snap=rig.command('REPEAT_OPEN_SIGNAL',iid,{'signal':'D15'})['snapshot']
    assert snap['signals']['D15']['aspect']=='B'
    assert snap['signals']['D1']['aspect']=='B'


@pytest.mark.parametrize('operation',['SWITCH_SINGLE_LOCK','SWITCH_SINGLE_UNLOCK','SWITCH_SEAL','SWITCH_UNSEAL'])
def test_point_flags_do_not_propagate_a_later_segment_fault_to_the_first_signal(operation):
    rig=Rig();rig.open('D1>S4')
    rig.command('SET_SECTION_OCCUPANCY','19DG',{'kind':'fault'})
    snap=rig.command(operation,'1')['snapshot']
    assert snap['signals']['D1']['aspect']=='B'
    assert snap['signals']['D15']['aspect'] is None


def test_second_fault_unlock_releases_only_the_requested_section_and_keeps_other_signal_open():
    rig=Rig();iid=rig.open('D1>S4')
    assert rig.command('SECTION_FAULT_UNLOCK','19DG')['reason_code']=='SIGNAL_CLOSED_LOCKS_HELD'
    assert rig.command('SECTION_FAULT_UNLOCK','19DG')['accepted']
    snap=rig.advance(30.1)
    assert snap['signals']['D1']['aspect']=='B'
    assert snap['signals']['D15']['aspect'] is None
    assert not snap['sections']['19DG']['locked']
    assert snap['sections']['27DG']['locked']
    assert snap['sections']['1DG']['owners']==[iid]
    assert rig.command('REPEAT_OPEN_SIGNAL',iid,{'signal':'D15'})['reason_code']=='SEGMENT_PARTLY_RELEASED'


@pytest.mark.parametrize('operation',['CANCEL_ROUTE','REPEAT_OPEN_SIGNAL','MANUAL_UNLOCK_ROUTE'])
def test_section_fault_unlock_timer_blocks_other_release_or_reopen_of_the_same_basic_segment(operation):
    rig=Rig();iid=rig.open('D1>S4')
    rig.command('SECTION_FAULT_UNLOCK','19DG')
    rig.command('SECTION_FAULT_UNLOCK','19DG')
    assert rig.command(operation,iid,{'signal':'D15'})['reason_code']=='UNLOCK_PENDING'
    assert rig.session.signals['D1']['aspect']=='B'


@pytest.mark.parametrize('definition',[r for r in console_station_package()['routes'] if r['attribute']==11],ids=lambda r:r['id'])
def test_local_guide_follows_preset_points_without_a_terminal_button(definition):
    rig=Rig();route=set_path(rig,definition)
    snap=rig.command('GUIDE_ARM',route['signal'])['snapshot']
    assert snap['selected_buttons']==[]
    assert len(snap['routes'])==1
    assert snap['routes'][0]['sections']==route['sections']
    snap=rig.advance(.7)
    assert snap['signals'][route['signal']]['aspect']=='HB'
    assert rig.advance(20)['signals'][route['signal']]['aspect']=='HB'


def test_guide_can_be_arranged_after_filament_failure_without_claiming_lamps_are_lit():
    rig=Rig();set_path(rig,'L_X>SIII')
    rig.command('SIGNAL_FILAMENT_BREAK','X')
    assert rig.command('GUIDE_ARM','X')['accepted']
    snap=rig.advance(.7)
    assert snap['signals']['X']['aspect']=='HB'
    assert snap['signals']['X']['filament_ok'] is False
    assert '无法点亮' in snap['last_message']


@pytest.mark.parametrize('position',[0,1])
def test_sealed_point_prevents_basic_route_even_when_position_already_matches(position):
    rig=Rig()
    if position:
        rig.command('SWITCH_TOTAL_REVERSE','1');rig.advance(2.1)
    rig.command('SWITCH_SEAL','1')
    assert not press(rig,'D1DA','D15DA')['accepted']


def test_unrepresented_point_prevents_basic_route():
    rig=Rig();rig.command('SET_SWITCH_INDICATION','1')
    assert not press(rig,'D1DA','D15DA')['accepted']


def test_basic_track_fault_requires_explicit_repeat_open_after_recovery():
    rig=Rig();reply=press(rig,'D1DA','D15DA')
    iid=reply['snapshot']['routes'][0]['id'];rig.advance(.7)
    snap=rig.command('SET_SECTION_OCCUPANCY','1DG',{'kind':'fault'})['snapshot']
    assert snap['signals']['D1']['aspect'] is None
    assert not rig.command('REPEAT_OPEN_SIGNAL',iid)['accepted']
    snap=rig.command('CLEAR_SECTION_OCCUPANCY','1DG')['snapshot']
    assert snap['signals']['D1']['aspect'] is None
    assert rig.command('REPEAT_OPEN_SIGNAL',iid)['snapshot']['signals']['D1']['aspect']=='B'


def test_terminal_alias_does_not_bypass_a_sealed_button():
    rig=Rig();assert rig.command('SIGNAL_SEAL','D15')['accepted']
    assert press(rig,'D1DA','D15DA')['reason_code']=='SIGNAL_BUTTON_SEALED'


def test_flank_demands_outside_the_vehicle_path_remain_locked():
    rig=Rig();iid=rig.open('D13>SII')
    snap=rig.advance(10)
    assert snap['switches']['23']['owners']==[iid]
    assert snap['switches']['25']['owners']==[iid]
    assert rig.command('SWITCH_TOTAL_REVERSE','23')['reason_code']=='SWITCH_ROUTE_LOCKED'


def test_ba1_variants_and_shunt_variants_keep_the_recorded_aspects():
    rig=Rig()
    assert press(rig,'SIIILA','BA1','XFLA')['accepted']
    rig.advance(2.1);snap=rig.advance(.7)
    assert snap['signals']['SIII']['aspect']=='L'
    rig=Rig()
    assert press(rig,'XLA','BA1','SIIILA')['accepted']
    rig.advance(2.1);snap=rig.advance(.7)
    assert snap['signals']['X']['aspect']=='UU'
    rig=Rig();rig.open('D7>D1')
    assert press(rig,'S4DA','D9DA')['accepted']
    rig.advance(2.1);snap=rig.advance(.7)
    assert snap['signals']['S4']['aspect']==snap['signals']['D7']['aspect']=='B'


def test_same_track_train_conflicts_and_guide_shunt_conflicts():
    rig=Rig();rig.open('L_S>XIII')
    assert not rig.route('L_X>SIII')['accepted']
    assert not rig.route('D12>XIII')['accepted']
    rig=Rig();set_path(rig,'L_X>SII')
    rig.command('GUIDE_ARM','X');rig.advance(.7)
    assert not rig.route('D8>XII')['accepted']


@pytest.mark.parametrize('section,kind',[('IIIG','vehicle'),('IIIG','fault'),('3DG','vehicle'),('3DG','fault')])
def test_train_cannot_accept_occupied_destination_or_internal_section(section,kind):
    rig=Rig();rig.command('SET_SECTION_OCCUPANCY',section,{'kind':kind})
    assert not rig.route('L_X>SIII')['accepted']


def test_route_fault_with_occupied_approach_cannot_be_cancelled_after_recovery():
    rig=Rig();iid=rig.open('D3>D7')
    rig.command('SET_SECTION_OCCUPANCY','3DG',{'kind':'fault'})
    rig.command('CLEAR_SECTION_OCCUPANCY','3DG')
    rig.command('SET_SECTION_OCCUPANCY','IAG',{'kind':'vehicle'})
    assert rig.session.signals['D3']['aspect'] is None
    assert not rig.command('CANCEL_ROUTE',iid)['accepted']


def test_vehicle_intrusion_stops_a_manual_unlock_timer():
    rig=Rig();iid=rig.open('L_X>SI')
    assert rig.command('MANUAL_UNLOCK_ROUTE',iid)['accepted']
    rig.command('SET_SECTION_OCCUPANCY','IAG',{'kind':'vehicle'})
    rig.command('CLEAR_SECTION_OCCUPANCY','IAG')
    snap=rig.advance(181)
    assert snap['sections']['5DG']['locked']
    assert any(e['kind']=='manual_unlock_intrusion' for e in snap['events'])


@pytest.mark.parametrize('definition',[r for r in console_station_package()['routes'] if r['attribute']==11],ids=lambda r:r['id'])
def test_total_guide_follows_actual_branches_and_avoids_unrelated_lost_indications(definition):
    rig=Rig();route=set_path(rig,definition)
    signal=rig.service._entry(route['signal'])
    spare=next(p['id'] for p in rig.service.package['switches']
               if p['id'] not in route['path_switches'] and p['mate'] not in route['path_switches']
               and p['throat']==signal['throat'])
    assert rig.command('SET_SWITCH_INDICATION',spare)['accepted']
    assert rig.command('GUIDE_TOTAL_LOCK',route['signal'])['accepted']
    assert rig.command('GUIDE_ARM',route['signal'])['accepted']
    snap=rig.advance(0)
    assert snap['signals'][route['signal']]['aspect']=='HB'
    assert snap['selected_buttons']==[]
    assert snap['routes'][0]['sections']==route['sections']
    iid=snap['routes'][0]['id']
    assert rig.command('SIMULATE_TRAIN_START',route['sections'][0],{'route_instance_id':iid})['accepted']
    snap=rig.advance((len(route['sections'])+3)*2+3.1)
    assert snap['routes'][0]['status']=='released'
    assert not snap['switches'][spare]['represented']
    assert route['signal'] in snap['guide_locks']


def test_total_guide_opens_but_cannot_simulate_through_a_lost_point():
    rig=Rig();set_path(rig,'L_X>SI')
    rig.command('SET_SWITCH_INDICATION','5')
    assert not rig.command('GUIDE_ARM','X')['accepted']
    assert rig.command('GUIDE_TOTAL_LOCK','X')['accepted']
    reply=rig.command('GUIDE_ARM','X')
    assert reply['accepted']
    assert reply['snapshot']['signals']['X']['aspect']=='HB'
    iid=reply['snapshot']['routes'][0]['id']
    assert rig.command('SIMULATE_TRAIN_START','IAG',{'route_instance_id':iid})['accepted']
    snap=rig.advance(6.1)
    assert not snap['routes'][0]['auto_running']
    assert snap['sections']['IAG']['occupied']
    assert not snap['sections']['5DG']['occupied']
    assert any(e['kind']=='rejected' and '5' in e['message'] for e in snap['events'])


def test_total_guide_can_be_added_after_normal_route_loses_indication():
    rig=Rig();set_path(rig,'L_X>SIII');iid=rig.open('L_X>SIII')
    # The device menu now forbids injecting this fault into a locked group.
    # Physical feedback protection still handles a real loss after arrangement.
    assert not rig.command('SET_SWITCH_INDICATION','5')['accepted']
    rig.session.switches['5'].update(represented=False, indication_fault=True)
    with rig.clock():
        rig.service._protect_point_signals(rig.session)
    assert rig.session.signals['X']['aspect'] is None
    assert not rig.command('GUIDE_ARM','X')['accepted']
    assert rig.command('GUIDE_TOTAL_LOCK','X')['accepted']
    assert rig.session.signals['X']['aspect'] is None
    snap=rig.command('GUIDE_ARM','X')['snapshot']
    assert snap['signals']['X']['aspect']=='HB'
    assert not rig.command('SWITCH_TOTAL_REVERSE','27')['accepted']
    assert rig.command('MANUAL_UNLOCK_ROUTE',iid)['accepted']
    assert rig.command('GUIDE_TOTAL_UNLOCK','X')['accepted']
    assert rig.session.routes[iid]['mode']=='normal'
    assert rig.session.sections['5DG']['owners']=={iid}


@pytest.mark.parametrize('name,section',[('L_X>SII','5DG'),('D11>S5','21DG')])
def test_first_fault_unlock_closes_signal_without_starting_any_release_timer(name,section):
    rig=Rig();iid=rig.open(name)
    result=rig.command('SECTION_FAULT_UNLOCK',section)
    assert result['accepted']
    assert result['reason_code']=='SIGNAL_CLOSED_LOCKS_HELD'
    snap=rig.advance(301)
    assert snap['signals'][rig.session.routes[iid]['signal']]['aspect'] is None
    assert snap['sections'][section]['locked']
    assert snap['fault_releases']=={}
    assert not any(e['kind']=='fault_unlock_complete' for e in snap['events'])


def test_guide_manual_unlock_requires_track_fault_to_be_cleared():
    rig=Rig();set_path(rig,'L_X>SIII')
    rig.command('SET_SECTION_OCCUPANCY','5DG',{'kind':'fault'})
    result=rig.command('GUIDE_ARM','X')
    assert result['accepted']
    iid=result['snapshot']['routes'][0]['id'];rig.advance(.7)
    assert not rig.command('MANUAL_UNLOCK_ROUTE',iid)['accepted']
    rig.command('CLEAR_SECTION_OCCUPANCY','5DG')
    assert rig.command('MANUAL_UNLOCK_ROUTE',iid)['accepted']
    assert rig.advance(180.1)['routes'][0]['status']=='released'


@pytest.mark.parametrize('kind',['vehicle','fault'])
def test_clearance_protection_still_closes_signal_for_an_actual_external_input(kind):
    rig=Rig();rig.open('D3>D11')
    snap=rig.command('SET_SECTION_OCCUPANCY','3DG',{'kind':kind})['snapshot']
    assert snap['signals']['D3']['aspect'] is None
    assert snap['sections']['3DG']['occupancy_kind']==kind
    assert snap['sections']['5DG']['locked']


def test_first_inner_fault_requires_15_second_hold_and_clearing_it_establishes_hold():
    rig=Rig();set_path(rig,'L_X>SII')
    rig.command('SET_SECTION_OCCUPANCY','IAG',{'kind':'fault'})
    assert rig.command('GUIDE_ARM','X')['accepted']
    assert rig.advance(.7)['signals']['X']['aspect']=='HB'
    assert rig.advance(14.9)['signals']['X']['aspect']=='HB'
    assert rig.advance(.2)['signals']['X']['aspect'] is None
    assert rig.command('GUIDE_ARM','X')['accepted']
    rig.command('CLEAR_SECTION_OCCUPANCY','IAG')
    assert rig.advance(20)['signals']['X']['aspect']=='HB'


def test_compound_route_cancel_and_manual_unlock_work_by_basic_segment():
    rig=Rig();iid=rig.open('D1>SI')
    rig.command('SET_SECTION_OCCUPANCY','IIAG',{'kind':'vehicle'})
    for signal in ['D13','D9']:
        assert rig.command('CANCEL_ROUTE',iid,{'signal':signal})['accepted']
        snap=rig.advance(.7)
        assert snap['signals'][signal]['aspect'] is None
        assert snap['signals']['D1']['aspect']=='B'
    assert not rig.command('CANCEL_ROUTE',iid,{'signal':'D1'})['accepted']
    assert rig.command('MANUAL_UNLOCK_ROUTE',iid,{'signal':'D1'})['accepted']
    assert rig.advance(29.9)['sections']['1DG']['locked']
    snap=rig.advance(.2)
    assert not snap['sections']['1DG']['locked']
    assert not snap['sections']['3DG']['locked']


@pytest.mark.parametrize('name,approach',[('L_X>SI','YXG'),('L_X>S5','YXG'),('L_SIII>XD','IIIG'),('L_SIII>XF','IIIG')])
def test_approached_train_requires_180_second_manual_unlock(name,approach):
    rig=Rig();iid=rig.open(name)
    rig.command('SET_SECTION_OCCUPANCY',approach,{'kind':'vehicle'})
    assert not rig.command('CANCEL_ROUTE',iid)['accepted']
    assert rig.command('MANUAL_UNLOCK_ROUTE',iid)['accepted']
    assert rig.advance(179.9)['routes'][0]['status']=='manual_unlocking'
    assert rig.advance(.2)['routes'][0]['status']=='released'


@pytest.mark.parametrize('name',['L_X>SI','L_X>S5','L_SIII>XD','L_SIII>XF'])
def test_unapproached_train_cancels_without_a_manual_countdown(name):
    rig=Rig();iid=rig.open(name)
    assert rig.command('CANCEL_ROUTE',iid)['accepted']
    snap=rig.advance(.7)
    assert snap['routes'][0]['status']=='cancelled'
    assert snap['routes'][0]['manual_remaining_seconds']==0
    assert not any(e['kind']=='manual_unlock_start' for e in snap['events'])


def test_manual_vehicle_inputs_release_the_same_path_as_automatic_movement():
    rig=Rig();iid=rig.open('D11>S5')
    rig.command('SET_SECTION_OCCUPANCY','7DG',{'kind':'vehicle'})
    rig.command('SET_SECTION_OCCUPANCY','13DG',{'kind':'vehicle'})
    snap=rig.command('CLEAR_SECTION_OCCUPANCY','7DG')['snapshot']
    assert snap['signals']['D11']['aspect'] is None
    rig.command('SET_SECTION_OCCUPANCY','11DG',{'kind':'vehicle'})
    snap=rig.command('CLEAR_SECTION_OCCUPANCY','13DG')['snapshot']
    assert snap['sections']['13DG']['clearing']
    assert rig.advance(1.01)['switches']['13']['branch_displays']==['idle']*3
    assert rig.advance(2.1)['sections']['13DG']['locked'] is False
    assert rig.session.routes[iid]['remaining']=={'11DG','21DG','5G'}


@pytest.mark.parametrize('entered_first',[False,True])
def test_partial_shunt_return_unlock_requires_actual_entry_into_the_basic_segment(entered_first):
    rig=Rig()
    route=rig.service.routes['SDM-062']
    iid=exact_open(rig,route)
    rig.command('SET_SECTION_OCCUPANCY','IIIG',{'kind':'vehicle'})
    path=route['sections']
    previous='IIIG'
    for name in path[:path.index('9DG')+1]:
        rig.command('SET_SECTION_OCCUPANCY',name,{'kind':'vehicle'})
        if name != '9DG':  # consist straddles independently insulated 9 and 15
            rig.command('CLEAR_SECTION_OCCUPANCY',previous)
        previous=name
        rig.advance(3.1)
    if entered_first:
        rig.command('SET_SECTION_OCCUPANCY','3DG',{'kind':'vehicle'})
        rig.command('CLEAR_SECTION_OCCUPANCY','3DG')
    # Fold back from the approach into a separate reception shunt. The
    # original unused tail must remain locked unless its first DG was entered.
    assert rig.route('D13>SII')['accepted']
    rig.advance(2.1);rig.advance(.7)
    rig.command('CLEAR_SECTION_OCCUPANCY','9DG')
    assert rig.advance(3.1)['sections']['3DG']['locked']
    rig.command('CLEAR_SECTION_OCCUPANCY','15DG')
    snap=rig.advance(3.1)
    assert snap['sections']['3DG']['locked'] is not entered_first
    if not entered_first:
        assert rig.command('CANCEL_ROUTE',iid,{'signal':'D7'})['accepted']
