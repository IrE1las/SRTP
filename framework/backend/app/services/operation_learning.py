"""Durable learning lifecycle; client submissions never supply logs or scores."""
from copy import deepcopy
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.models.operation import OperationQuestion, OperationVersion, OperationSession
from app.models.operation_learning import OperationAttempt, OperationReview
from app.services import operations as ops
from app.services.operation_comparison import compare


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def owned(db, user, sid):
    item = db.get(OperationAttempt, sid)
    if not item or (user.role == 'student' and item.student_id != user.id):
        ops.fail('作答不存在或无权查看', 404)
    if user.role not in {'student', 'teacher', 'admin'}:
        ops.fail('无权查看', 403)
    return item


def public_question(item, sealed):
    snapshot = deepcopy(item.question_snapshot)
    if not sealed:
        snapshot.pop('standard_log', None)
        snapshot.pop('standard_session_id', None)
    return snapshot


def review_data(db, sid):
    row = db.get(OperationReview, sid)
    return {'revision': row.revision, 'comment': row.comment, 'confirmed': row.confirmed,
            'reviewer_id': row.reviewer_id,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None} if row else {
                'revision': 0, 'comment': None, 'confirmed': False, 'reviewer_id': None, 'updated_at': None}


def summary(db, item):
    session = db.get(OperationSession, item.session_id)
    return {'session_id': item.session_id, 'question_id': item.question_id,
            'question': {k: item.question_snapshot[k] for k in ('title', 'number')},
            'identity': item.identity_snapshot, 'student_id': item.student_id,
            'status': session.status, 'created_at': session.created_at,
            'submitted_at': item.submitted_at, 'outcome': item.outcome,
            'ai_status': item.ai_status, 'review': review_data(db, item.session_id)}


def detail(db, user, sid):
    item = owned(db, user, sid)
    session = db.get(OperationSession, sid)
    sealed = session.status == 'submitted'
    if user.role == 'student':
        console = ops.refresh(db, user, sid)
    else:
        console = ops.view_session(db, user, sid)
    return {**summary(db, item), 'question': public_question(item, sealed or user.role != 'student'),
            'console': console, 'ai_text': item.ai_text}


def visible_version(db, user, qid):
    q = db.get(OperationQuestion, qid)
    v = db.scalar(select(OperationVersion).where(OperationVersion.question_id == qid,
            OperationVersion.number == q.published_version)) if q and q.published_version else None
    if not q or q.disabled or not v or not user.class_name or user.class_name not in v.classes:
        ops.fail('题目不存在、已停用或未向本班发布', 404)
    if v.station_version != ops.station_version():
        ops.fail('标准站版本已变化，请联系教师重新发布题目')
    return q, v


def begin(db, user, qid, restart_from=None):
    key = f'{user.id}:{qid}'
    if restart_from:
        previous = owned(db, user, restart_from)
        if previous.question_id != qid:
            ops.fail('重做记录不属于此题', 422)
        retry = db.scalar(select(OperationAttempt).where(OperationAttempt.previous_session_id == restart_from))
        if retry:
            return detail(db, user, retry.session_id)
    current = db.scalar(select(OperationAttempt).where(OperationAttempt.active_key == key))
    if current and not restart_from:
        return detail(db, user, current.session_id)
    if current and restart_from != current.session_id:
        ops.fail('已有另一份进行中的作答，请恢复当前作答')
    q, v = visible_version(db, user, qid)
    if current:
        claimed = db.execute(update(OperationSession).where(OperationSession.id == current.session_id,
            OperationSession.status == 'active').values(status='abandoned'))
        if claimed.rowcount != 1:
            db.rollback()
            ops.fail('作答状态已变化，请重新加载')
        current.active_key = None
        db.flush()
    engine = ops.ReferenceSimulationService(ops.reference_station_package())
    initial = deepcopy(v.initial)
    snap = engine.new_session(user.id, initial.get('interval_available', True), initial.get('occupied_sections', []))
    sid = snap['session_id']
    record = OperationSession(id=sid, owner_id=user.id, version_id=v.id, kind='learning',
        engine_state=ops.persistent_state(engine, sid), initial_snapshot=initial, station_version=v.station_version)
    db.add(record)
    db.flush()
    db.add(OperationAttempt(session_id=sid, question_id=qid, student_id=user.id, active_key=key,
        previous_session_id=restart_from, question_snapshot=ops.detail(q, v),
        identity_snapshot={'real_name': user.real_name, 'student_id': user.student_id, 'class_name': user.class_name}))
    db.add(OperationReview(session_id=sid))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        ops.fail('已有并发开始请求，请重新进入以恢复作答')
    return detail(db, user, sid)


def submit(db, user, sid):
    item = owned(db, user, sid)
    session = db.get(OperationSession, sid)
    if session.status == 'submitted':
        return detail(db, user, sid)
    if session.status != 'active':
        ops.fail('已放弃的作答不能提交')
    outcome = compare(item.question_snapshot['standard_log'], ops.events(db, sid))
    claimed = db.execute(update(OperationSession).where(OperationSession.id == sid,
        OperationSession.status == 'active', OperationSession.revision == session.revision,
        OperationSession.state_revision == session.state_revision).values(status='submitted'))
    if claimed.rowcount != 1:
        db.rollback()
        ops.fail('作答刚有新操作，请同步后提交')
    item.outcome = outcome
    item.active_key = None
    item.submitted_at = now()
    db.commit()
    return detail(db, user, sid)


def list_attempts(db, user, page, class_name='', student_number='', question_id=None, question_search=''):
    statement = select(OperationAttempt).join(OperationSession)
    if user.role == 'student':
        statement = statement.where(OperationAttempt.student_id == user.id)
    else:
        statement = statement.where(OperationSession.status == 'submitted')
    if question_id is not None:
        statement = statement.where(OperationAttempt.question_id == question_id)
    rows = []
    for item in db.scalars(statement.order_by(OperationSession.created_at.desc(), OperationAttempt.session_id.desc())):
        identity = item.identity_snapshot
        if class_name and identity.get('class_name') != class_name:
            continue
        if student_number.strip() and student_number.strip() not in (identity.get('student_id') or ''):
            continue
        if question_search.strip().casefold() not in (item.question_snapshot.get('title') or '').casefold():
            continue
        rows.append(summary(db, item))
    return {'items': rows[(page - 1) * 6:page * 6], 'page': page, 'page_size': 6, 'total': len(rows)}


def save_review(db, user, sid, body):
    item = owned(db, user, sid)
    if not item.submitted_at:
        ops.fail('只能评阅已提交的操作答卷')
    row = db.get(OperationReview, sid)
    if row.revision != body.revision:
        ops.fail('另一位教师已更新评阅，请刷新后修改')
    values = {'comment': (body.comment or '').strip() or None, 'confirmed': body.confirmed,
              'reviewer_id': user.id, 'updated_at': now(), 'revision': row.revision + 1}
    audit = deepcopy(row.audit)
    audit.append({**values, 'updated_at': values['updated_at'].isoformat()})
    changed = db.execute(update(OperationReview).where(OperationReview.session_id == sid,
        OperationReview.revision == body.revision).values(**values, audit=audit))
    if changed.rowcount != 1:
        db.rollback()
        ops.fail('评阅保存冲突，请刷新后修改')
    db.commit()
    return detail(db, user, sid)


def download(db, user, sid):
    item = owned(db, user, sid)
    session = db.get(OperationSession, sid)
    if user.role == 'student' and session.status != 'submitted':
        ops.fail('提交后才能下载学习日志')
    return {'schema_version': 1, 'kind': 'learning', 'session_id': sid,
            'station_version': session.station_version, 'question_id': item.question_id,
            'question_version': item.question_snapshot['number'],
            'question': public_question(item, session.status == 'submitted' or user.role != 'student'),
            'initial': session.initial_snapshot, 'status': session.status,
            'submitted_at': item.submitted_at.isoformat() if item.submitted_at else None,
            'events': ops.events(db, sid), 'outcome': item.outcome,
            'ai_text': item.ai_text, 'ai_status': item.ai_status,
            'review': review_data(db, sid)}
