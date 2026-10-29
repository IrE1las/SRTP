"""Lossless persistence adapter; standard-station business rules stay untouched."""
from dataclasses import fields
from time import monotonic, time
from app.services.simulation_console.runtime import RuntimeSession
from app.services.simulation_console.reference_runtime import ReferenceSimulationService

TIMER_KEYS = {'selection_deadline', 'manual_release_due', 'signal_open_due',
              'guide_deadline', 'due', 'deadline'}
TIMER_MAPS = {'release_due', 'fault_releases'}


def transform(value, offset, key=''):
    if isinstance(value, set):
        return {'__runtime_set__': sorted(value)}
    if isinstance(value, dict):
        return {k: transform(v, offset, k) if key not in TIMER_MAPS else
                v + offset if isinstance(v, (int, float)) else v for k, v in value.items()}
    if isinstance(value, list):
        return [transform(item, offset) for item in value]
    if key in TIMER_KEYS and value is not None:
        return value + offset
    return value


def restore_sets(value):
    if isinstance(value, dict):
        if set(value) == {'__runtime_set__'}:
            return set(value['__runtime_set__'])
        return {k: restore_sets(v) for k, v in value.items()}
    if isinstance(value, list):
        return [restore_sets(v) for v in value]
    return value


def pack(engine, sid):
    session = engine.sessions[sid]
    data = {f.name: getattr(session, f.name) for f in fields(RuntimeSession)
            if f.name not in {'mutex', 'history'}}
    # Process-local monotonic deadlines become absolute UTC deadlines, including
    # point motion, track proving, cancellation, guide hold and fault release.
    return transform({'session': data, 'reference': engine._state(session)}, time() - monotonic())


def unpack(package, data):
    restored = restore_sets(transform(data, monotonic() - time()))
    engine = ReferenceSimulationService(package)
    session = RuntimeSession(**restored['session'])
    engine.sessions[session.id] = session
    engine.reference_states[session.id] = restored['reference']
    return engine, session
