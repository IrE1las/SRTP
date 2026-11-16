from copy import deepcopy
from datetime import timezone
from sqlalchemy import select
from app.models.operation import OperationSession, OperationEvent
from app.models.exam import Exam
from app.models.operation_assessment import ExamEvidenceSeal, ExamEvaluation
from app.services.operation_runtime import unpack
from app.services.operation_assessment import evidence, scorer
from app.services.simulation_console import clock


def latest(db, sid):
    return db.scalar(select(ExamEvaluation).where(ExamEvaluation.session_id == sid)
                     .order_by(ExamEvaluation.version.desc()).limit(1))


def view(db, sid):
    from app.core.config import settings
    if not settings.operation_assessment_enabled:
        return None
    row = latest(db, sid)
    return {'id': row.id, 'version': row.version, **deepcopy(row.content)} if row else None


def seal(db, attempt, cutoff):
    """The caller owns the serialized exam transaction. Failure never reopens an exam."""
    from app.services import operations as ops
    if db.get(ExamEvidenceSeal, attempt.session_id):
        return
    exam = db.get(Exam, attempt.exam_id)
    config = (exam.question_snapshot or {}).get('assessment')
    if not config:
        return
    record = db.get(OperationSession, attempt.session_id)
    content = {'cutoff_at': cutoff.replace(tzinfo=timezone.utc).isoformat(),
               'configuration_digest': config['fingerprint'], 'engine_version': evidence.engine_version(),
               'station_version': record.station_version, 'status': 'ready'}
    try:
        if config['engine_version'] != content['engine_version'] or record.station_version != ops.station_version():
            raise ValueError('站场或运行版本发生变化，请人工复核')
        if record.engine_state.get('evidence_schema') != 1:
            raise ValueError('此答卷不具备新版业务证据')
        with clock.at(cutoff):
            engine, session = unpack(ops.reference_station_package(), record.engine_state)
            evidence.advance(db, record, engine, session)
            evidence.persist(db, record, engine, session)
            content['final_state'] = deepcopy(record.engine_state['session'])
        events = evidence.rows(db, record.id)
        clicks = list(db.scalars(select(OperationEvent).where(OperationEvent.session_id == record.id)
                                .order_by(OperationEvent.sequence)))
        content.update(evidence_count=len(events), evidence_digest=events[-1].digest if events else None,
                       click_count=record.revision, click_digest=evidence.digest([c.content for c in clicks]))
        if not evidence.validate(events) or [c.sequence for c in clicks] != list(range(1, record.revision + 1)):
            raise ValueError('事件序号或完整性校验未通过')
        source_ids = [r.content['source']['event_id'] for r in events if r.content.get('source')]
        if source_ids != [r.event_id for r in clicks]:
            raise ValueError('点击与业务变化的关联不完整')
    except ValueError as exc:
        content.update(status='needs_review', reason=str(exc))
    row = ExamEvidenceSeal(session_id=attempt.session_id, content=content, digest=evidence.digest(content))
    db.add(row)
    db.flush()
    evaluate(db, attempt)


def evaluate(db, attempt):
    from app.core.config import settings
    if not settings.operation_assessment_enabled:
        return None
    exam = db.get(Exam, attempt.exam_id)
    config = (exam.question_snapshot or {}).get('assessment')
    if not config:
        return None
    seal_row = db.get(ExamEvidenceSeal, attempt.session_id)
    if not seal_row:
        return None
    sealed = seal_row.content
    rows = evidence.rows(db, attempt.session_id)
    clicks = list(db.scalars(select(OperationEvent).where(OperationEvent.session_id == attempt.session_id)
                            .order_by(OperationEvent.sequence)))
    fingerprint = evidence.digest({'seal': seal_row.digest, 'observed_seal': evidence.digest(sealed),
        'observed_events': [evidence.digest(r.content) for r in rows], 'event_sequences': [r.sequence for r in rows],
        'clicks': [r.content for r in clicks], 'config': config, 'scorer': scorer.RUBRIC_VERSION})
    old = db.scalar(select(ExamEvaluation).where(ExamEvaluation.session_id == attempt.session_id,
                                              ExamEvaluation.fingerprint == fingerprint))
    if old:
        return {'id': old.id, 'version': old.version, **deepcopy(old.content)}
    valid = (evidence.digest(sealed) == seal_row.digest and evidence.validate(rows) and
             len(rows) == sealed.get('evidence_count') and
             (rows[-1].digest if rows else None) == sealed.get('evidence_digest') and
             evidence.digest([r.content for r in clicks]) == sealed.get('click_digest') and
             config['fingerprint'] == evidence.digest({k:v for k,v in config.items() if k!='fingerprint'}))
    if sealed['status'] != 'ready':
        result = scorer.review(sealed.get('reason', '截止状态无法确认'))
    elif not valid:
        result = scorer.review('封存证据已变化或不完整，请人工复核')
    else:
        result = scorer.score(config, [{'sequence': r.sequence, 'content': r.content} for r in rows], sealed['final_state'])
    result['cutoff_at'] = sealed['cutoff_at']
    previous = latest(db, attempt.session_id)
    row = ExamEvaluation(session_id=attempt.session_id, version=previous.version + 1 if previous else 1,
                         fingerprint=fingerprint, content=result)
    db.add(row)
    db.flush()
    return view(db, attempt.session_id)
