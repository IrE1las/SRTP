"""Free console: physical circuits, scissors protection and context commands.

Use a virtual clock through the public command boundary. Existing assessment
runtime tests intentionally keep using the unmodified reference package.
"""
from contextlib import contextmanager
from copy import deepcopy

import pytest

from app.services.simulation_console.clock import at
from app.services.simulation_console.console_commands import operate
from app.services.simulation_console.console_runtime import ConsoleSimulationService
from app.services.simulation_console.console_station import console_station_package
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.runtime import SimulationError


class Rig:
    def __init__(self):
        self.time = 1000.
        self.service = ConsoleSimulationService(console_station_package())
        with at(self.time):
            snap = self.service.new_session(31)
        self.session = self.service._get(snap['session_id'], 31)

    @contextmanager
    def clock(self):
        with at(self.time):
            yield

    def command(self, kind, target, payload=None):
        with self.clock():
            return operate(self.service, self.session.id, 31,
                           {'type': kind, 'target': target, 'payload': payload or {}, 'pin': '0000'}, self.session.version)

    def route(self, name):
        definition = next(r for r in self.service.package['routes'] if r['name'] == name)
        with self.clock():
            for button in definition['button_sequence']:
                result = self.service.select_button(self.session.id, 31, button, self.session.version)
        return result

    def advance(self, seconds):
        self.time += seconds
        with self.clock():
            return self.service.snapshot(self.session.id, 31)

    def open(self, name):
        result = self.route(name)
        assert result['accepted'], result['message']
        iid = result['snapshot']['routes'][-1]['id']
        self.advance(2.1)
        snap = self.advance(.7)
        assert self.session.routes[iid]['status'] == 'signal_open', snap['last_message']
        return iid


def test_console_compilation_is_private_and_does_not_add_unused_dg():
    before = deepcopy(reference_station_package())
    package = console_station_package()
    assert package['counts']['sections'] == 42
    assert package['counts']['ready_routes'] == 199
    assert next(r for r in package['routes'] if r['name'] == 'XI>D12')['sections'] == ['16DG']
    assert next(r for r in package['routes'] if r['name'] == 'D18>D12')['sections'] == ['22DG', '20DG', '18DG', '16DG']
    assert reference_station_package() == before
    assert before['counts']['sections'] == 35
    assert next(p for p in before['switches'] if p['id'] == '16')['section'] == '16-18DG'


@pytest.mark.parametrize('first,other', [('6', '10'), ('10', '6'), ('13', '9'), ('9', '13')])
def test_scissors_protection_blocks_movement_without_fake_occupancy(first, other):
    rig = Rig()
    assert rig.command('SWITCH_TOTAL_REVERSE', first)['accepted']
    snap = rig.advance(2.1)
    assert snap['switches'][other]['cross_protected']
    assert not any(s['occupied'] for s in snap['sections'].values())
    assert rig.command('SWITCH_TOTAL_REVERSE', other)['reason_code'] == 'CROSSOVER_PROTECTED'
    assert rig.command('SWITCH_TOTAL_NORMAL', first)['accepted']
    rig.advance(2.1)
    assert rig.command('SWITCH_TOTAL_REVERSE', other)['accepted']


def test_16dg_input_is_independent_of_18dg_and_feedback_is_per_end():
    rig = Rig()
    snap = rig.command('SET_SECTION_OCCUPANCY', '16DG', {'kind': 'vehicle'})['snapshot']
    assert snap['sections']['16DG']['occupied']
    assert not snap['sections']['18DG']['occupied']
    assert rig.command('SWITCH_TOTAL_REVERSE', '16')['reason_code'] == 'SECTION_OCCUPIED'
    assert rig.command('SWITCH_TOTAL_REVERSE', '18')['accepted']
    rig.advance(2.1)
    rig.command('SET_SWITCH_INDICATION', '16')
    snap = rig.command('RESTORE_SWITCH_INDICATION', '16', {'position': 1})['snapshot']
    assert snap['switches']['16']['reverse_indication']
    assert snap['switches']['18']['reverse_indication']
    snap = rig.command('RESTORE_SWITCH_INDICATION', '16', {'position': 0})['snapshot']
    assert snap['switches']['16']['normal_indication']


@pytest.mark.parametrize('first,second,terminal', [
    ('D1>D5', 'SII>D15', '1/19WG'),
    ('D13>SI', 'D12>XI', 'IG'),
    ('D15>SII', 'D6>XII', 'IIG'),
    ('D1>SI', 'D8>XI', 'IG'),  # composed long-shunt route
])
def test_opposing_shunts_share_only_the_non_point_terminal(first, second, terminal):
    rig = Rig()
    a = rig.open(first)
    b = rig.open(second)
    snap = rig.advance(5)
    assert set(snap['sections'][terminal]['owners']) == {a, b}
    for iid in (a, b):
        assert snap['signals'][rig.session.routes[iid]['signal']]['aspect'] == 'B'
    definition = rig.service.routes[rig.session.routes[a]['route_id']]
    signals = [rig.service.routes[c]['signal'] for c in definition['subroutes']] or [definition['signal']]
    for signal in signals:
        result = rig.command('CANCEL_ROUTE', a, {'signal': signal})
        assert result['accepted'], result['message']
        snap = rig.advance(.7)
    assert snap['sections'][terminal]['owners'] == [b]
    assert snap['signals'][rig.session.routes[b]['signal']]['aspect'] == 'B'


def test_train_conflicts_path_overlaps_and_faults_remain_protected():
    rig = Rig()
    rig.open('D13>SI')
    assert not rig.route('L_S>XI')['accepted']
    assert not rig.route('D9>SI')['accepted']
    rig = Rig()
    rig.command('SET_SECTION_OCCUPANCY', 'IG', {'kind': 'fault'})
    assert rig.route('D12>XI')['accepted']
    assert rig.session.sections['IG']['occupancy_kind'] == 'fault'
    rig = Rig()
    rig.command('SET_SECTION_OCCUPANCY', '16DG', {'kind': 'fault'})
    assert not rig.route('D12>XI')['accepted']
    rig.command('CLEAR_SECTION_OCCUPANCY', '16DG')
    rig.command('SET_SECTION_OCCUPANCY', 'IG', {'kind': 'vehicle'})
    assert rig.route('D12>XI')['accepted']


def test_context_train_target_green_for_one_second_then_gray_with_lock_retained():
    rig = Rig()
    iid = rig.open('D12>XI')
    payload = {'route_instance_id': iid}
    assert rig.command('SIMULATE_TRAIN_STEP', '18DG', payload)['reason_code'] == 'ROUTE_TARGET_MISMATCH'
    assert rig.command('SIMULATE_TRAIN_STEP', '16DG', payload)['accepted']  # approach
    result = rig.command('SIMULATE_TRAIN_STEP', '16DG', payload)  # 16DG
    assert result['accepted']
    assert result['snapshot']['sections']['16DG']['occupied']
    assert not result['snapshot']['sections']['18DG']['occupied']
    result = rig.command('SIMULATE_TRAIN_STEP', '16DG', payload)  # IG, 16 clears
    assert result['snapshot']['sections']['16DG']['clearing']
    assert rig.advance(.99)['sections']['16DG']['clearing']
    snap = rig.advance(.02)
    assert not snap['sections']['16DG']['clearing']
    assert not snap['sections']['16DG']['display_locked']
    assert not snap['sections']['16DG']['occupied']
    assert snap['sections']['16DG']['locked']  # visual timing does not release locks early
    assert snap['switches']['16']['branch_displays'] == ['idle']*3
    assert not rig.advance(2.01)['sections']['16DG']['locked']
    with rig.clock(), pytest.raises(SimulationError):
        rig.service.step_train(rig.session.id, 999, iid)


def test_restore_wrong_position_closes_existing_signal_and_does_not_reopen_it():
    rig = Rig()
    rig.open('D12>XI')
    result = rig.command('RESTORE_SWITCH_INDICATION', '16', {'position': 1})
    assert result['snapshot']['signals']['D12']['aspect'] is None
    assert result['snapshot']['switches']['16']['locked']
    result = rig.command('RESTORE_SWITCH_INDICATION', '16', {'position': 0})
    assert result['snapshot']['signals']['D12']['aspect'] is None


def test_crossing_route_normalizes_opposite_diagonal_before_reversing():
    rig = Rig()
    rig.command('SWITCH_TOTAL_REVERSE', '10')
    rig.advance(2.1)
    result = rig.route('D6>XI')
    assert result['accepted'], result['message']
    snap = rig.advance(2.1)
    assert snap['switches']['10']['normal_indication']
    assert snap['switches']['6']['moving']
    assert snap['signals']['D6']['aspect'] is None
    rig.advance(.1)  # start the protected diagonal after normal feedback
    snap = rig.advance(2.1)
    assert snap['switches']['6']['reverse_indication']
    assert snap['signals']['D6']['aspect'] is None
    snap = rig.advance(.7)
    assert snap['signals']['D6']['aspect'] == 'B'


def test_compatible_coupled_point_owners_keep_both_signals_open():
    rig = Rig()
    a = rig.open('D3>D7')
    b = rig.open('L_XD>S5')
    snap = rig.advance(5)
    for sid in ('5', '7'):
        assert set(snap['switches'][sid]['owners']) == {a, b}
    assert snap['signals']['D3']['aspect'] == 'B'
    assert snap['signals']['XD']['aspect'] == 'UU'


def test_all_199_definitions_still_arrange_drive_and_release():
    for definition in console_station_package()['routes']:
        rig = Rig()
        # Select the exact original row: duplicate names/button sequences must
        # not silently cause this sweep to retest the first alternative.
        with rig.clock():
            result = rig.service._arrange(rig.session, definition)
        assert result['accepted'], (definition['id'], result['message'])
        iid = result['snapshot']['routes'][-1]['id']
        assert rig.session.routes[iid]['route_id'] == definition['id']
        rig.advance(2.1)
        rig.advance(.7)
        assert rig.session.routes[iid]['status'] == 'signal_open', definition['id']
        instance = rig.session.routes[iid]
        for _ in range(len(definition['movement_groups'])+1+int(instance['progress'] == -2)):
            with rig.clock():
                result = rig.service.step_train(rig.session.id, 31, iid, rig.session.version)
            assert result['accepted'], (definition['name'], result['message'])
        snap = rig.advance(3.1)
        assert snap['routes'][0]['status'] == 'released', definition['name']
        assert not any(s['locked'] for s in snap['sections'].values())
        assert not any(s['locked'] for s in snap['switches'].values())
