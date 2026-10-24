"""Regressions from the 2026-10-24 native CPOINT/renderer audit.

Drive the public command boundary with a clock, never sleeps. The native
branch probes remain separate evidence; these tests verify our implementation.
"""
import pytest

from app.services.simulation_console import console_commands, reference_runtime, runtime
from app.services.simulation_console.reference_station import reference_station_package


@pytest.fixture
def rig(monkeypatch):
    clock = [1000.]
    for module in (runtime, reference_runtime, console_commands):
        monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    svc = reference_runtime.ReferenceSimulationService(reference_station_package())
    snap = svc.new_session(31)
    return svc, svc._get(snap['session_id'], 31), clock


def command(rig, kind, target, **extra):
    svc, session, _ = rig
    return console_commands.operate(svc, session.id, 31,
                                    {'type': kind, 'target': target, **extra}, session.version)


def route(rig, name):
    svc, session, _ = rig
    definition = next(r for r in svc.package['routes'] if r['name'] == name)
    for button in definition['button_sequence']:
        result = svc.select_button(session.id, 31, button, session.version)
    return result


def advance(rig, seconds):
    svc, session, clock = rig
    clock[0] += seconds
    return svc.snapshot(session.id, 31)


def shared_routes(rig):
    assert route(rig, 'D3>D7')['accepted']
    first = next(iter(rig[1].routes))
    result = route(rig, 'L_XD>S5')
    assert result['accepted'], result['message']
    second = next(reversed(rig[1].routes))
    snap = advance(rig, 2.1)
    assert snap['signals']['D3']['aspect'] == 'B'
    assert snap['signals']['XD']['aspect'] == 'UU'
    for sid in ('5', '7'):
        assert set(snap['switches'][sid]['owners']) == {first, second}
    return first, second


def test_pair_command_flashes_without_falsifying_feedback_then_reaches_target(rig):
    result = command(rig, 'SWITCH_TOTAL_REVERSE', '5')
    assert result['accepted']
    for sid in ('5', '7'):
        point = result['snapshot']['switches'][sid]
        assert point['position'] == 0 and point['target_position'] == 1
        assert point['moving'] and not point['represented']
        assert not point['normal_indication'] and not point['reverse_indication']
    assert advance(rig, 1.9)['switches']['5']['moving']
    assert command(rig, 'SWITCH_SINGLE_LOCK', '5')['reason_code'] == 'SWITCH_MOVING'
    snap = advance(rig, .2)
    assert all(snap['switches'][sid]['reverse_indication'] for sid in ('5', '7'))
    assert command(rig, 'SWITCH_TOTAL_NORMAL', '7')['snapshot']['switches']['5']['target_position'] == 0
    snap = advance(rig, 2.1)
    assert all(snap['switches'][sid]['normal_indication'] for sid in ('5', '7'))


def test_route_reserves_resources_but_never_opens_or_runs_before_feedback(rig):
    result = route(rig, 'D9>S5')
    assert result['accepted']
    instance = result['snapshot']['routes'][0]
    assert instance['status'] == 'setting'
    assert result['snapshot']['signals']['D9']['aspect'] is None
    assert result['snapshot']['sections']['21DG']['locked']
    svc, session, _ = rig
    result = svc.step_train(session.id, 31, instance['id'], session.version)
    assert result['reason_code'] == 'ROUTE_SETTING'
    assert command(rig, 'REPEAT_OPEN_SIGNAL', instance['id'])['reason_code'] == 'ROUTE_SETTING'
    snap = advance(rig, 2.1)
    assert snap['routes'][0]['status'] == 'signal_open'
    assert snap['signals']['D9']['aspect'] == 'B'


def test_one_end_failure_times_out_without_overwriting_its_mate(rig):
    assert route(rig, 'D9>S5')['accepted']
    # 9/15 must reverse for this route. Only 9's feedback is interrupted.
    assert command(rig, 'SET_SWITCH_INDICATION', '9')['accepted']
    snap = advance(rig, 2.1)
    assert snap['switches']['15']['represented'] and not snap['switches']['15']['moving']
    assert snap['switches']['9']['moving'] and not snap['switches']['9']['represented']
    assert snap['signals']['D9']['aspect'] is None
    snap = advance(rig, 11)
    assert snap['switches']['9']['movement_failed'] and not snap['switches']['9']['moving']
    assert snap['routes'][0]['status'] == 'closed_locked'
    assert snap['sections']['21DG']['locked']
    iid = snap['routes'][0]['id']
    # Restoring an old normal indication is not proof of reverse alignment.
    assert command(rig, 'RESTORE_SWITCH_INDICATION', '9')['accepted']
    result = command(rig, 'REPEAT_OPEN_SIGNAL', iid)
    assert not result['accepted'] and result['reason_code'] == 'SWITCH_POSITION_MISMATCH'
    assert result['snapshot']['signals']['D9']['aspect'] is None


def test_restored_feedback_before_deadline_finishes_pending_route(rig):
    assert route(rig, 'D9>S5')['accepted']
    command(rig, 'SET_SWITCH_INDICATION', '9')
    advance(rig, 3)
    result = command(rig, 'RESTORE_SWITCH_INDICATION', '9')
    assert result['snapshot']['switches']['9']['reverse_indication']
    assert result['snapshot']['signals']['D9']['aspect'] == 'B'


@pytest.mark.parametrize('operation', ['CANCEL_ROUTE', 'MANUAL_UNLOCK_ROUTE', 'SECTION_FAULT_UNLOCK', 'normal'])
def test_releasing_one_shared_route_preserves_the_other_owner(rig, operation):
    first, second = shared_routes(rig)
    svc, session, _ = rig
    if operation == 'normal':
        instance = session.routes[first]
        for _ in range(len(instance['sections']) + 1 + int(instance['progress'] == -2)):
            result = svc.step_train(session.id, 31, first, session.version)
            assert result['accepted']
        snap = advance(rig, 3.1)
    elif operation == 'SECTION_FAULT_UNLOCK':
        result = command(rig, operation, '5DG', pin='0000')
        assert result['accepted']
        snap = advance(rig, 31)
    else:
        result = command(rig, operation, first, pin='0000')
        assert result['accepted']
        snap = advance(rig, 31) if operation == 'MANUAL_UNLOCK_ROUTE' else result['snapshot']
    for sid in ('5', '7'):
        # The section release may retain this route's other end, but it must
        # never erase the adjacent route's ownership of either end.
        assert second in snap['switches'][sid]['owners']
        if operation != 'SECTION_FAULT_UNLOCK':
            assert first not in snap['switches'][sid]['owners']
    assert snap['signals']['XD']['aspect'] == 'UU'
    result = command(rig, 'SWITCH_TOTAL_REVERSE', '5')
    assert not result['accepted'] and result['reason_code'] == 'SWITCH_ROUTE_LOCKED'


def test_shared_routes_still_reject_opposite_position_and_section_conflicts(rig):
    shared_routes(rig)
    svc, session, _ = rig
    same = next(r for r in svc.package['routes'] if r['name'] == 'L_XD>S5')
    # Isolate the point-owner rule: equal demands can share, opposite cannot.
    assert svc._switch_lock_fact(session, same, next(reversed(session.routes))) is None
    conflict = {**same, 'switches': {**same['switches'], '5': 1, '7': 1}}
    assert svc._switch_lock_fact(session, conflict)[0] == 'SWITCH_ROUTE_LOCKED'
    assert not route(rig, 'D3>D7')['accepted']


def test_shared_point_feedback_fault_closes_both_signals_without_losing_locks(rig):
    first, second = shared_routes(rig)
    snap = command(rig, 'SET_SWITCH_INDICATION', '5')['snapshot']
    assert not snap['switches']['5']['represented']
    assert snap['switches']['7']['normal_indication']
    assert snap['signals']['D3']['aspect'] is None and snap['signals']['XD']['aspect'] is None
    assert set(snap['switches']['5']['owners']) == {first, second}
    snap = command(rig, 'RESTORE_SWITCH_INDICATION', '5')['snapshot']
    assert snap['signals']['D3']['aspect'] is None
    assert command(rig, 'REPEAT_OPEN_SIGNAL', first)['accepted']
    assert command(rig, 'REPEAT_OPEN_SIGNAL', second)['accepted']


def test_same_position_sharing_works_in_reverse_arrangement_order(rig):
    assert route(rig, 'L_XD>S5')['accepted']
    advance(rig, 2.1)
    assert route(rig, 'D3>D7')['accepted']
    snap = advance(rig, 0)
    assert snap['signals']['XD']['aspect'] == 'UU' and snap['signals']['D3']['aspect'] == 'B'
    assert len(snap['switches']['5']['owners']) == len(snap['switches']['7']['owners']) == 2


def test_manual_release_of_partially_cancelled_composite_closes_remaining_signal(rig):
    result = route(rig, 'D1>S5')
    snap = advance(rig, 2.1)
    iid = result['snapshot']['routes'][0]['id']
    snap = command(rig, 'CANCEL_ROUTE', iid, payload={'signal': 'D1'})['snapshot']
    assert snap['signals']['D9']['aspect'] == 'B'
    snap = command(rig, 'MANUAL_UNLOCK_ROUTE', iid, pin='0000')['snapshot']
    assert snap['signals']['D9']['aspect'] is None
    assert snap['routes'][0]['status'] == 'manual_unlocking'
    assert any(point['locked'] for point in snap['switches'].values())


@pytest.mark.parametrize('fault', ['occupied', 'unrepresented', 'sealed', 'manual_mismatch'])
def test_same_position_sharing_does_not_bypass_other_guards(rig, fault):
    assert route(rig, 'D3>D7')['accepted']
    svc, session, _ = rig
    if fault == 'occupied':
        session.sections['7DG']['occupied'] = True
    elif fault == 'unrepresented':
        command(rig, 'SET_SWITCH_INDICATION', '5')
    elif fault == 'sealed':
        command(rig, 'SWITCH_SEAL', '5')
    else:
        session.switches['5'].update(position=1, manual_locked=True)
    svc.snapshot(session.id, 31)
    assert not route(rig, 'L_XD>S5')['accepted']
    assert not any(s.get('aspect') for name,s in session.signals.items() if name == 'XD')


def test_pending_route_rechecks_track_condition_and_cancellation_cannot_reopen(rig):
    result = route(rig, 'D9>S5')
    iid = result['snapshot']['routes'][0]['id']
    command(rig, 'SET_SECTION_OCCUPANCY', '21DG', payload={'kind':'fault'})
    snap = advance(rig, 2.1)
    assert snap['routes'][0]['status'] == 'closed_locked'
    assert snap['signals']['D9']['aspect'] is None
    command(rig, 'CLEAR_SECTION_OCCUPANCY', '21DG')
    assert command(rig, 'CANCEL_ROUTE', iid)['accepted']
    assert advance(rig, 20)['signals']['D9']['aspect'] is None


def test_cancelling_during_conversion_never_opens_later(rig):
    result = route(rig, 'D9>S5')
    iid = result['snapshot']['routes'][0]['id']
    assert command(rig, 'CANCEL_ROUTE', iid)['accepted']
    snap = advance(rig, 3)
    assert snap['routes'][0]['status'] == 'cancelled'
    assert snap['signals']['D9']['aspect'] is None
    assert not any(p['locked'] for p in snap['switches'].values())


def test_experiment_service_keeps_instant_alignment_and_exclusive_ownership(rig):
    svc = runtime.SimulationService()
    snap = svc.new_session(31)
    session = svc._get(snap['session_id'], 31)
    result = console_commands.operate(svc, session.id, 31,
                                     {'type':'SWITCH_TOTAL_REVERSE', 'target':'5'}, session.version)
    assert result['accepted'] and result['snapshot']['switches']['5']['position'] == 1
    assert 'moving' not in result['snapshot']['switches']['5']
    definition = next(r for r in svc.package['routes'] if '5' in r['switches'])
    session.switches['5']['owners'].add('existing-experiment-lock')
    assert svc._switch_lock_fact(session, definition)[0] == 'SWITCH_ROUTE_LOCKED'
