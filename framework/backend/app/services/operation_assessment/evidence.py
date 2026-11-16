"""Append-only transition evidence and chronological timer advancement."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from sqlalchemy import select
from app.models.operation_assessment import OperationEvidenceEvent
from app.services.operation_runtime import pack
from app.services.simulation_console import clock


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def engine_version():
    directory = Path(__file__).parent.parent / 'simulation_console'
    files = sorted(directory.glob('*.py')) + [Path(__file__).parent.parent / 'operation_runtime.py']
    return digest({p.name: sha256(p.read_bytes()).hexdigest() for p in files})


def state(engine, sid):
    data = pack(engine, sid)
    # Small hint cache only. The complete history is in OperationEvidenceEvent.
    data['session']['events'] = data['session']['events'][-10:]
    data['evidence_schema'] = 1
    data['evaluated_at'] = clock.time()
    return data


def persist(db, record, engine, session, source=None):
    previous = record.engine_state or {}
    last_version = previous.get('session', {}).get('version', -1)
    emitted = [deepcopy(e) for e in session.events if e['version'] > last_version]
    data = state(engine, session.id)
    before = previous.get('session', {})
    delta = {}
    for key in ('routes', 'switches', 'sections', 'signals'):
        changes = {k: v for k, v in data['session'][key].items() if before.get(key, {}).get(k) != v}
        if changes:
            delta[key] = changes
    selection = data['session']['selected']
    if selection != before.get('selected', []):
        delta['selected'] = selection
    if emitted or source or delta:
        prior = db.scalar(select(OperationEvidenceEvent).where(OperationEvidenceEvent.session_id == session.id)
                          .order_by(OperationEvidenceEvent.sequence.desc()).limit(1))
        content = {'schema_version': 1, 'at': clock.iso(), 'source': source,
                   'events': emitted, 'delta': delta, 'previous_digest': prior.digest if prior else None}
        db.add(OperationEvidenceEvent(session_id=session.id, sequence=prior.sequence + 1 if prior else 1,
                                      content=content, digest=digest(content)))
        db.flush()
    record.engine_state = data
    session.events = session.events[-10:]
    return data


def rows(db, sid):
    return list(db.scalars(select(OperationEvidenceEvent).where(OperationEvidenceEvent.session_id == sid)
                          .order_by(OperationEvidenceEvent.sequence)))


def due_times(engine, session):
    return _due_times(session, engine._state(session))


def due_epochs(package):
    """Persisted deadlines are UTC epochs; inspection need not instantiate an engine."""
    from types import SimpleNamespace
    return _due_times(SimpleNamespace(**package['session']), package['reference'])


def _due_times(session, reference):
    timers = []
    if session.selected and session.selection_deadline is not None:
        timers.append(session.selection_deadline)
    for sid, motion in reference['point_motions'].items():
        timers.append(motion['deadline'] if session.switches[sid].get('indication_fault') else motion['due'])
    timers.extend(reference['fault_releases'].values())
    for route in session.routes.values():
        if route['status'] in {'cancelled', 'released'}:
            continue
        for key in ('signal_open_due', 'manual_release_due'):
            if route.get(key) is not None:
                timers.append(route[key])
        pending = route.get('cancel_pending') or {}
        if pending.get('due') is not None:
            timers.append(pending['due'])
        timers.extend(route.get('release_due', {}).values())
        if route.get('mode') == 'guide' and session.signals[route['signal']].get('aspect') == 'HB':
            timers.append(route['guide_deadline'])
    return timers


def advance(db, record, engine, session, target=None):
    """Advance at each scheduled instant; never use late observation as completion."""
    target = clock.time() if target is None else target
    start = record.engine_state.get('evaluated_at', target)
    if target < start - 0.00001:
        raise ValueError('截止时点早于已记录的业务状态，需人工复核')
    # Offsets remain stable under the request-local virtual clock.
    with clock.at(target):
        offset = clock.time() - clock.monotonic()
    blocked = set()
    for _ in range(10000):
        candidates = [max(start, value + offset) for value in due_times(engine, session)
                      if value + offset <= target and value not in blocked]
        if not candidates:
            break
        at = min(candidates)
        old = session.version
        with clock.at(at):
            engine.snapshot(session.id, session.owner_id)
            if session.version != old:
                persist(db, record, engine, session)
                blocked.clear()
            else:
                # A timer whose condition remains blocked must not loop forever.
                blocked.update(v for v in due_times(engine, session) if v + offset <= at)
        start = at
    else:
        raise ValueError('自动状态推进超过界限，需人工复核')
    with clock.at(target):
        old = session.version
        engine.snapshot(session.id, session.owner_id)
        if session.version != old:
            persist(db, record, engine, session)


def validate(events):
    previous = None
    for number, row in enumerate(events, 1):
        if row.sequence != number or row.content.get('previous_digest') != previous or digest(row.content) != row.digest:
            return False
        previous = row.digest
    return True
