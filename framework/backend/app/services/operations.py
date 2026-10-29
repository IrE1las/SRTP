"""S3 authoring and durable, ordered business clicks. No grading or AI calls."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from threading import RLock
from time import time
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from app.models.operation import OperationQuestion, OperationVersion, OperationSession, OperationEvent
from app.services.operation_runtime import pack, unpack
from app.services.simulation_console.reference_station import reference_station_package
from app.services.simulation_console.reference_runtime import ReferenceSimulationService
from app.services.simulation_console.console_commands import operate, SEALED_COMMANDS
from app.services.simulation_console.runtime import SimulationError

# The HTTP protocol is shared by future student attempts. Presets and peer
# inputs deliberately have no click command, even for a teacher recording.
COMMAND_TARGETS = {
    'CANCEL_ROUTE': 'route', 'MANUAL_UNLOCK_ROUTE': 'route', 'REPEAT_OPEN_SIGNAL': 'route',
    'SECTION_FAULT_UNLOCK': 'section', 'GUIDE_ARM': 'signal', 'GUIDE_MAINTAIN': 'signal',
    'GUIDE_TOTAL_LOCK': 'signal', 'GUIDE_TOTAL_UNLOCK': 'signal',
    'SWITCH_TOTAL_NORMAL': 'switch', 'SWITCH_TOTAL_REVERSE': 'switch',
    'SWITCH_SINGLE_LOCK': 'switch', 'SWITCH_SINGLE_UNLOCK': 'switch',
    'SWITCH_SEAL': 'switch', 'SWITCH_UNSEAL': 'switch', 'SIGNAL_SEAL': 'signal',
    'SIGNAL_UNSEAL': 'signal', 'SIGNAL_LIGHT_ON': 'signal', 'SIGNAL_LIGHT_OFF': 'signal',
    'BLOCK_REQUEST': 'block', 'BLOCK_RESET': 'block', 'BLOCK_ACCIDENT_RESET': 'block',
    'BLOCK_DEPARTURE_AUX': 'block', 'BLOCK_RECEPTION_AUX': 'block', 'BLOCK_TOTAL_AUX': 'block',
}
LOCK = RLock()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def station_version():
    return digest(reference_station_package())


def persistent_state(engine, sid, previous=None):
    data = pack(engine, sid)
    audit = list((previous or {}).get('runtime_events', []))
    last = audit[-1]['version'] if audit else -1
    audit.extend(deepcopy(e) for e in engine.sessions[sid].events if e['version'] > last)
    data['runtime_events'] = audit
    return data


def fail(message, status=409):
    raise HTTPException(status, message)


def question(db, user, qid):
    q = db.get(OperationQuestion, qid)
    if not q or user.role not in {'teacher', 'admin'}:
        fail('题目不存在或无权管理', 404)
    return q


def delete_question(db, user, qid):
    q = question(db, user, qid)
    from app.models.operation_learning import OperationAttempt
    from app.models.exam import Exam
    version_ids = select(OperationVersion.id).where(OperationVersion.question_id == qid)
    if db.scalar(select(Exam.id).where(Exam.version_id.in_(version_ids)).limit(1)):
        fail('该题目已有考试引用，不能永久删除；请停用题目以保留历史依据')
    if db.scalar(select(OperationAttempt.session_id).where(OperationAttempt.question_id == qid).limit(1)):
        fail('该题目已有学生作答引用，不能永久删除；请停用题目以保留历史依据')
    session_ids = select(OperationSession.id).where(OperationSession.version_id.in_(version_ids))
    if db.scalar(select(OperationSession.id).where(OperationSession.version_id.in_(version_ids), OperationSession.status == 'active').limit(1)):
        fail('请先结束该题目的所有录制和预览，再删除')
    db.execute(delete(OperationEvent).where(OperationEvent.session_id.in_(session_ids)), execution_options={'synchronize_session': False})
    db.execute(delete(OperationSession).where(OperationSession.version_id.in_(version_ids)), execution_options={'synchronize_session': False})
    db.execute(delete(OperationVersion).where(OperationVersion.question_id == qid), execution_options={'synchronize_session': False})
    db.delete(q)
    db.commit()
    return {'deleted': True, 'id': qid}


def latest(db, qid):
    return db.scalar(select(OperationVersion).where(OperationVersion.question_id == qid)
                     .order_by(OperationVersion.number.desc()).limit(1))


def validate_draft(body):
    data = body.model_dump(exclude={'revision'})
    data['title'] = (data['title'] or '').strip() or None
    data['prompt'] = (data['prompt'] or '').strip() or None
    classes = [item.strip() for item in data['classes']]
    if any(not name or len(name) > 100 for name in classes):
        fail('班级名称不能为空且不得超过100字', 422)
    data['classes'] = list(dict.fromkeys(classes))
    initial = data['initial']
    known = {s['name'] for s in reference_station_package()['sections']}
    if any(name not in known for name in initial['occupied_sections']):
        fail('预置占用包含标准站之外的区段', 422)
    initial['occupied_sections'] = list(dict.fromkeys(initial['occupied_sections']))
    return data


def detail(q, v, include_standard=True):
    result = {'id': q.id, 'owner_id': q.owner_id, 'disabled': q.disabled,
              'published_version': q.published_version, 'version_id': v.id,
              'number': v.number, 'status': 'disabled' if q.disabled else v.status,
              'revision': v.revision, 'title': v.title, 'prompt': v.prompt,
              'classes': v.classes, 'initial': v.initial, 'station_version': v.station_version,
              'published_at': v.published_at.isoformat() if v.published_at else None}
    if include_standard:
        result.update(standard_log=v.standard_log, standard_session_id=v.standard_session_id)
    return result


def create(db, user, body):
    data = validate_draft(body)
    q = OperationQuestion(owner_id=user.id)
    db.add(q)
    db.flush()
    v = OperationVersion(question_id=q.id, number=1, station_version=station_version(), **data)
    db.add(v)
    db.commit()
    return detail(q, v)


def edit(db, user, qid, body):
    q = question(db, user, qid)
    if q.disabled:
        fail('已停用题目不能修改；请新建题目')
    v = latest(db, qid)
    if v.revision != body.revision:
        fail('题目已变化，请重新加载后编辑')
    if db.scalar(select(OperationSession.id).where(OperationSession.version_id == v.id,
            OperationSession.status == 'active', OperationSession.kind.in_(['recording', 'preview'])).limit(1)):
        fail('请先结束该版本的录制或预览，再修改题设')
    data = validate_draft(body)
    if v.status == 'published':
        v = OperationVersion(question_id=qid, number=v.number + 1, station_version=station_version(), **data)
        db.add(v)
    else:
        old_revision = v.revision
        changed_initial = data['initial'] != v.initial
        values = {**data, 'revision': old_revision + 1}
        if changed_initial:
            values.update(standard_log=None, standard_session_id=None)
        updated = db.execute(update(OperationVersion).where(OperationVersion.id == v.id,
            OperationVersion.revision == old_revision).values(**values))
        if updated.rowcount != 1:
            db.rollback()
            fail('题目被其他请求修改，请刷新')
        db.expire(v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail('新版本已由其他请求建立，请刷新')
    return detail(q, v)


def publish(db, user, qid):
    q = question(db, user, qid)
    v = latest(db, qid)
    if q.disabled:
        fail('题目已停用')
    if v.status == 'published':
        return detail(q, v)
    if not v.title or not v.prompt or not v.classes:
        fail('发布需要标题、题干和目标班级')
    if db.scalar(select(OperationSession.id).where(OperationSession.version_id == v.id,
            OperationSession.status == 'active').limit(1)):
        fail('请先结束录制和预览，再发布')
    if v.station_version != station_version():
        fail('标准站版本已变化，请重新录制新版本')
    recording = db.get(OperationSession, v.standard_session_id) if v.standard_session_id else None
    if not recording or recording.status != 'stopped' or recording.kind != 'recording' or not v.standard_log:
        fail('请先结束录制并保存非空标准日志')
    if recording.version_id != v.id or recording.initial_snapshot != v.initial:
        fail('标准录制与当前题设不一致')
    if any(e['action'] == 'function' and e['button_id'] not in {*COMMAND_TARGETS, 'CLEAR_SELECTION'}
           for e in v.standard_log):
        fail('标准日志包含学生无权执行的操作')
    if not any(e['action'] in {'button', 'target'} and e['result']['accepted'] for e in v.standard_log):
        fail('标准日志须至少包含一次有效业务目标操作')
    claimed = db.execute(update(OperationVersion).where(OperationVersion.id == v.id,
        OperationVersion.revision == v.revision, OperationVersion.status == 'draft').values(
            status='published', published_at=datetime.now(timezone.utc), revision=v.revision + 1))
    if claimed.rowcount != 1:
        db.rollback()
        fail('题目在发布期间已变化，请重新核对后发布')
    q.published_version = v.number
    db.commit()
    return detail(q, v)


def list_questions(db, user, page, search='', status='all'):
    statement = select(OperationQuestion)
    if user.role == 'student':
        statement = statement.where(OperationQuestion.disabled.is_(False),
                                    OperationQuestion.published_version.is_not(None))
    rows = []
    for q in db.scalars(statement.order_by(OperationQuestion.id.desc())):
        v = latest(db, q.id) if user.role != 'student' else db.scalar(select(OperationVersion).where(
            OperationVersion.question_id == q.id, OperationVersion.number == q.published_version))
        if user.role == 'student' and (not user.class_name or user.class_name not in v.classes):
            continue
        row = detail(q, v, include_standard=False)
        # Lists do not preload answers. Students never receive standard logs or session IDs.
        if status != 'all' and row['status'] != status:
            continue
        term = search.strip().casefold()
        if term and not any(term in str(value or '').casefold() for value in [v.title, *v.classes]):
            continue
        rows.append(row)
    if user.role == 'student':
        rows.sort(key=lambda row: (row['published_at'] or '', row['id']), reverse=True)
    return {'items': rows[(page - 1) * 6: page * 6], 'total': len(rows), 'page': page, 'page_size': 6}


def view_session(db, user, sid):
    record = db.get(OperationSession, sid)
    if not record:
        fail('会话不存在', 404)
    if record.kind == 'exam':
        fail('请通过有权限的考试详情查看考试记录', 404)
    version = db.get(OperationVersion, record.version_id)
    question(db, user, version.question_id)
    if record.owner_id == user.id and record.kind != 'learning':
        return {**refresh(db, user, sid), 'read_only': False}
    if record.station_version != station_version():
        fail('站场版本已变化，请下载原日志查看')
    engine, session = unpack(reference_station_package(), record.engine_state)
    return {**response(db, record, engine, session), 'read_only': True}


def get_session(db, user, sid, *, exam=False):
    record = db.get(OperationSession, sid)
    if not record:
        fail('会话不存在或无权访问', 404)
    v = db.get(OperationVersion, record.version_id)
    if record.kind == 'exam':
        if not exam or user.role != 'student':
            fail('考试会话只能通过考试接口访问', 404)
    elif record.kind == 'learning':
        from app.models.operation_learning import OperationAttempt
        attempt = db.get(OperationAttempt, sid)
        if user.role != 'student' or not attempt or attempt.student_id != user.id:
            fail('学习会话不存在或无权操作', 404)
    else:
        question(db, user, v.question_id)
    # Course data are shared; live commands remain bound to the originating operator.
    if record.owner_id != user.id:
        fail('该操作台属于另一位录制人', 404)
    if record.station_version != station_version():
        fail('运行规则版本已变化，原日志保留；请新建版本录制')
    return record


def events(db, sid):
    return [deepcopy(row.content) for row in db.scalars(select(OperationEvent).where(
        OperationEvent.session_id == sid).order_by(OperationEvent.sequence))]


def response(db, record, engine, session):
    snapshot = engine._snapshot(session)
    pending = deepcopy(record.context.get('pending'))
    if pending and pending['expires_at'] <= time():
        pending = None
    snapshot.update(pending=pending, click_sequence=record.revision,
                    session_status=record.status, session_kind=record.kind)
    return {'snapshot': snapshot, 'events': events(db, record.id), 'status': record.status,
            'pending': pending, 'revision': record.revision, 'session_id': record.id}


def start_session(db, user, qid, kind):
    q = question(db, user, qid)
    v = latest(db, qid)
    if q.disabled or (kind == 'recording' and v.status != 'draft'):
        fail('仅草稿可录制，已停用题目不能开始新会话')
    if v.station_version != station_version():
        fail('站场版本已变化，请保存新题目版本')
    # A teacher may record again; previous active console is sealed, never overwritten.
    for previous in db.scalars(select(OperationSession).where(OperationSession.version_id == v.id,
            OperationSession.owner_id == user.id, OperationSession.status == 'active',
            OperationSession.kind.in_(['recording', 'preview']))):
        previous.status = 'abandoned'
    engine = ReferenceSimulationService(reference_station_package())
    initial = deepcopy(v.initial)
    snap = engine.new_session(user.id, initial.get('interval_available', True), initial.get('occupied_sections', []))
    sid = snap['session_id']
    record = OperationSession(id=sid, owner_id=user.id, version_id=v.id, kind=kind,
        engine_state=persistent_state(engine, sid), initial_snapshot=initial, station_version=v.station_version)
    db.add(record)
    db.commit()
    return response(db, record, engine, engine.sessions[sid])


def refresh(db, user, sid, *, exam=False, commit=True):
    record = get_session(db, user, sid, exam=exam)
    engine, session = unpack(reference_station_package(), record.engine_state)
    if record.status == 'active':
        engine.snapshot(sid, user.id)
        claimed = db.execute(update(OperationSession).where(OperationSession.id == sid,
            OperationSession.state_revision == record.state_revision,
            OperationSession.revision == record.revision, OperationSession.status == 'active').values(
                engine_state=persistent_state(engine, sid, record.engine_state),
                state_revision=OperationSession.state_revision + 1))
        if claimed.rowcount != 1:
            db.rollback()
            fail('会话已变化，请重新同步')
        db.commit() if commit else db.flush()
    return response(db, record, engine, session)


def click(db, user, sid, body, *, exam=False, commit=True):
    record = get_session(db, user, sid, exam=exam)
    clean = body.model_dump(mode='json', exclude={'pin', 'event_id', 'sequence'})
    fingerprint = digest(clean)
    previous = db.scalar(select(OperationEvent).where(OperationEvent.session_id == sid,
                                                      OperationEvent.event_id == str(body.event_id)))
    if previous:
        if previous.request_fingerprint != fingerprint or previous.sequence != body.sequence:
            fail('同一事件ID不得改换动作或序号')
        result = refresh(db, user, sid, exam=exam, commit=commit)
        result['event'] = previous.content
        return result
    if record.status != 'active':
        fail('操作记录已封存，不得追加操作')
    if body.sequence != record.revision + 1:
        fail('操作序号不连续，请同步会话后重试')
    if body.action == 'function' and body.button_id not in {*COMMAND_TARGETS, 'CLEAR_SELECTION'}:
        fail('该按钮不属于学生可用的业务操作', 422)
    if body.action == 'button' and body.button_id not in {b['name'] for b in reference_station_package()['buttons']}:
        fail('未知站场按钮', 422)
    if body.action == 'target':
        package = reference_station_package()
        known = {'signal': {s['name'] for s in package['signals']},
                 'switch': {s['id'] for s in package['switches']},
                 'section': {s['name'] for s in package['sections']},
                 'block': {s['signal'] for s in package['blocks']}}
        if body.target_id not in known[body.target_kind]:
            fail('目标不在当前标准站设备中', 422)
    engine, session = unpack(reference_station_package(), record.engine_state)
    engine.snapshot(sid, user.id)
    context = deepcopy(record.context)
    if context.get('pending') and context['pending']['expires_at'] <= time():
        context['pending'] = None
    result = {'accepted': True, 'message': '操作方式已选择'}
    target = body.target_id
    button = body.button_id
    parameters = {}
    try:
        if body.action == 'function':
            if button == 'CLEAR_SELECTION':
                context['pending'] = None
                result = engine.clear_selection(sid, user.id)
            else:
                context['pending'] = {'type': button, 'target': COMMAND_TARGETS[button], 'expires_at': time() + 15}
        elif body.action == 'cancel_selection':
            context['pending'] = None
            result = {'accepted': True, 'message': '未完成的功能选择已取消'}
        elif body.action == 'button' and not context.get('pending'):
            result = engine.select_button(sid, user.id, button)
            target = next((b.get('signal') for b in engine.package['buttons'] if b['name'] == button), None)
        else:
            pending = context.get('pending')
            if body.action == 'button':
                target = engine.buttons[button].get('signal')
                target_kind = 'signal'
            else:
                target_kind = body.target_kind
            if not pending:
                result = {'accepted': False, 'message': '请先选择功能按钮'}
            elif target_kind != ('signal' if pending['target'] == 'route' else pending['target']):
                result = {'accepted': False, 'message': '目标类型不符，请选择' + pending['target']}
            else:
                kind = pending['type']
                actual_target = target
                if pending['target'] == 'route':
                    instance = next((r for r in session.routes.values() if
                        r['status'] not in {'released', 'cancelled'} and target in
                        engine.routes[r['route_id']]['segment_signals']), None)
                    if instance:
                        actual_target = instance['id']
                        parameters = {'signal': target}
                        target = 'route:' + instance['route_id']
                    else:
                        result = {'accepted': False, 'message': '该信号没有仍锁闭的进路'}
                        actual_target = None
                if actual_target:
                    result = operate(engine, sid, user.id, {'type': kind, 'target': actual_target,
                        'payload': parameters, 'pin': body.pin}, None)
                context['pending'] = None
                # Keep the function in the target event as well; IDs are definitions, never UUIDs.
                button = kind
    except SimulationError as exc:
        result = {'accepted': False, 'message': str(exc)}
    content = {'schema_version': 1, 'event_id': str(body.event_id), 'session_id': sid,
               'sequence': body.sequence, 'action': body.action, 'button_id': button,
               'target_id': target, 'parameters': {**parameters, **({'target_kind': body.target_kind} if body.action == 'target' else {})},
               'event_time': datetime.now(timezone.utc).isoformat(),
               'engine_version': session.version,
               'result': {'accepted': bool(result['accepted']), 'message': result['message']}}
    # Atomic revision claim + unique constraints cover concurrent workers; a
    # losing request rolls back its event and station state together.
    claimed = db.execute(update(OperationSession).where(OperationSession.id == sid,
        OperationSession.revision == record.revision, OperationSession.state_revision == record.state_revision,
        OperationSession.status == 'active').values(revision=body.sequence,
        state_revision=OperationSession.state_revision + 1,
        engine_state=persistent_state(engine, sid, record.engine_state), context=context))
    if claimed.rowcount != 1:
        db.rollback()
        fail('另一个请求已修改会话，请同步后重试')
    db.add(OperationEvent(session_id=sid, event_id=str(body.event_id), sequence=body.sequence,
                          request_fingerprint=fingerprint, content=content))
    try:
        db.commit() if commit else db.flush()
    except IntegrityError:
        db.rollback()
        fail('操作发生并发冲突，请以相同事件ID重试')
    db.refresh(record)
    output = response(db, record, engine, session)
    output['event'] = content
    return output


def stop(db, user, sid):
    record = get_session(db, user, sid)
    if record.status == 'active':
        record.status = 'stopped'
        db.commit()
    return refresh(db, user, sid)


def save_standard(db, user, sid):
    record = get_session(db, user, sid)
    v = db.get(OperationVersion, record.version_id)
    if record.kind != 'recording' or record.status != 'stopped' or v.status != 'draft':
        fail('请先结束草稿版本的标准录制')
    log = events(db, sid)
    if not log:
        fail('空日志不能保存为标准答案')
    if v.initial != record.initial_snapshot:
        fail('题设已变化，请重新录制')
    claimed = db.execute(update(OperationVersion).where(OperationVersion.id == v.id,
        OperationVersion.revision == v.revision, OperationVersion.status == 'draft').values(
            standard_log=log, standard_session_id=sid, revision=v.revision + 1))
    if claimed.rowcount != 1:
        db.rollback()
        fail('保存期间题目已变化，请重新核对')
    db.commit()
    return detail(db.get(OperationQuestion, v.question_id), v)


def download(db, user, sid):
    record = db.get(OperationSession, sid)
    if not record:
        fail('日志不存在或无权访问', 404)
    if record.kind == 'exam':
        fail('请通过有权限的考试下载接口访问', 404)
    v = db.get(OperationVersion, record.version_id)
    q = question(db, user, v.question_id)
    return {'schema_version': 1, 'station_version': record.station_version,
            'question_id': q.id, 'question_version': v.number, 'session_id': sid,
            'kind': record.kind, 'status': record.status,
            'initial': record.initial_snapshot, 'events': events(db, sid),
            'runtime_events': record.engine_state.get('runtime_events', [])}
