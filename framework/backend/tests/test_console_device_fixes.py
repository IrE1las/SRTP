"""Device-menu restrictions and one-shot train clearance display."""
import pytest

from tests.test_free_console_behaviour import Rig
from app.services.simulation_console.console_station import console_station_package


@pytest.mark.parametrize('name', ['L_X>SI', 'L_S>XI', 'D3>D11', 'D11>S5'])
def test_auto_train_only_marks_the_section_just_cleared_green(name):
    rig = Rig(); iid = rig.open(name)
    instance = rig.session.routes[iid]
    rig.command('SIMULATE_TRAIN_START', instance['sections'][0], {'route_instance_id': iid})
    previous = []
    started = rig.time
    for step in range(len(instance['sections'])+2):
        snap = rig.advance(started+2*(step+1)-rig.time)
        current = [n for n,s in snap['sections'].items() if s['occupancy_kind'] == 'vehicle']
        newly_clear = set(previous)-set(current)
        assert {n for n,s in snap['sections'].items() if s['clearing']} == newly_clear
        for point in rig.service.package['switches']:
            green = 'clearing' in snap['switches'][point['id']]['branch_displays']
            assert not green or point['section'] in newly_clear
        snap = rig.advance(.99)
        assert {n for n,s in snap['sections'].items() if s['clearing']} == newly_clear
        snap = rig.advance(.02)
        assert not any(s['clearing'] for s in snap['sections'].values())
        previous = current
    assert rig.advance(3.1)['routes'][0]['status'] == 'released'


@pytest.mark.parametrize('point', [p['id'] for p in console_station_package()['switches']])
def test_indication_loss_and_restore_operate_the_whole_pair(point):
    rig = Rig(); mate = rig.service.switch_defs[point]['mate']
    group = {point, mate}-{''}
    result = rig.command('SET_SWITCH_INDICATION', point)
    assert result['accepted']
    assert {n for n,s in result['snapshot']['switches'].items() if not s['represented']} == group
    for position in (1,0):
        result = rig.command('RESTORE_SWITCH_INDICATION', point, {'position':position})
        assert result['accepted']
        assert all(result['snapshot']['switches'][n]['represented'] and
                   result['snapshot']['switches'][n]['position'] == position for n in group)


@pytest.mark.parametrize('point', ['6', '8', '6/8', '8/6'])
def test_one_remaining_locked_end_protects_the_whole_pair_from_fault_injection(point):
    rig = Rig(); iid = rig.open('L_S>XI')
    rig.command('SIMULATE_TRAIN_START', 'IIBG', {'route_instance_id':iid})
    snap = rig.advance(11.1)
    assert not snap['switches']['6']['owners']
    assert snap['switches']['8']['owners'] == [iid]
    result = rig.command('SET_SWITCH_INDICATION', point)
    assert not result['accepted'] and result['reason_code'] == 'SWITCH_ROUTE_LOCKED'
    assert all(result['snapshot']['switches'][n]['represented'] for n in ['6','8'])
    assert all(not result['snapshot']['switches'][n]['indication_fault_allowed'] for n in ['6','8'])


def test_total_guide_path_also_disables_menu_fault_injection():
    rig = Rig()
    assert rig.command('GUIDE_TOTAL_LOCK', 'X')['accepted']
    assert rig.command('GUIDE_ARM', 'X')['accepted']
    assert rig.command('SET_SWITCH_INDICATION', '7')['reason_code'] == 'SWITCH_ROUTE_LOCKED'
    assert rig.command('SET_SWITCH_INDICATION', '27')['accepted']


def test_repeated_successor_inputs_do_not_restart_the_old_green_or_release_timer():
    rig = Rig(); iid = rig.open('L_X>SI')
    for name in ['IAG','5DG']:
        rig.command('SET_SECTION_OCCUPANCY', name, {'kind':'vehicle'})
    rig.command('CLEAR_SECTION_OCCUPANCY','IAG')
    rig.advance(1.1)
    snap = rig.command('SET_SECTION_OCCUPANCY','3DG',{'kind':'vehicle'})['snapshot']
    assert not snap['sections']['IAG']['clearing']
    snap = rig.advance(2)
    assert iid not in snap['sections']['IAG']['owners']
