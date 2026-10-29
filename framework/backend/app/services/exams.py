"""Server-clock exams, serialized SQLite mutations, and idempotent sealing. No AI/grading."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select, text
from app.models import User
from app.models.exam import Exam, ExamParticipant, ExamAttempt, ExamControlEvent
from app.models.operation import OperationQuestion, OperationVersion, OperationSession, OperationEvent
from app.services import operations as ops
from app.services.operation_runtime import unpack

COMPLETED = '考试已完成，待教师确认并发布考试成绩'
REASONS = {'manual': '主动交卷', 'deadline': '考试时间到',
           'fullscreen_timeout': '退出全屏超时', 'fullscreen_limit': '超过全屏退出次数'}


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value else None


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


@contextmanager
def atomic(db):
    # Authentication already opened a read transaction. Acquire a write lock
    # before reading exam state, including across workers/windows and the sweeper.
    db.commit()
    if db.bind.dialect.name != 'sqlite':
        raise RuntimeError('S5考试事务当前仅支持本项目的SQLite数据库')
    db.execute(text('BEGIN IMMEDIATE'))
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def managed(db, user, eid):
    exam = db.get(Exam, eid)
    if not exam or user.role not in {'teacher', 'admin'} or (user.role == 'teacher' and exam.owner_id != user.id):
        ops.fail('考试不存在或无权管理', 404)
    return exam


def owned(db, user, sid):
    attempt = db.get(ExamAttempt, sid)
    if not attempt:
        ops.fail('考试答卷不存在或无权访问', 404)
    if user.role == 'student':
        if attempt.student_id != user.id:
            ops.fail('考试答卷不存在或无权访问', 404)
    else:
        managed(db, user, attempt.exam_id)
    return attempt


def page(rows, number):
    return {'items': rows[(number - 1) * 6:number * 6], 'page': number, 'page_size': 6, 'total': len(rows)}


def draft_values(body):
    values = body.model_dump(exclude={'revision'})
    values['name'] = (values['name'] or '').strip() or None
    values['classes'] = list(dict.fromkeys(x.strip() for x in values['classes']))
    if any(not x or len(x) > 100 for x in values['classes']):
        ops.fail('班级名称不能为空或超过100字', 422)
    for key in ('opens_at', 'closes_at'):
        values[key] = utc(values[key])
    if values['opens_at'] and values['closes_at'] and values['opens_at'] >= values['closes_at']:
        ops.fail('开放时间必须早于截止时间', 422)
    return values


def validate_version(db, vid):
    v = db.get(OperationVersion, vid) if vid else None
    q = db.get(OperationQuestion, v.question_id) if v else None
    if not v or not q or q.disabled or v.status != 'published' or not v.standard_log:
        ops.fail('请选择未停用操作题的已发布版本')
    if v.station_version != ops.station_version():
        ops.fail('标准站版本已变化，请先重新发布操作题')
    return q, v


def configuration(db, exam):
    return {'id': exam.id, 'owner_id': exam.owner_id, 'status': exam.status, 'revision': exam.revision,
            'name': exam.name, 'classes': exam.classes, 'version_id': exam.version_id,
            'opens_at': iso(exam.opens_at), 'closes_at': iso(exam.closes_at),
            'duration_minutes': exam.duration_minutes, 'published_at': iso(exam.published_at),
            'participant_count': db.query(ExamParticipant).filter_by(exam_id=exam.id).count(),
            'attempt_count': db.query(ExamAttempt).filter_by(exam_id=exam.id).count(),
            'question': deepcopy(exam.question_snapshot)}


def create(db, user, body):
    values = draft_values(body)
    if values['version_id'] is not None and not db.get(OperationVersion, values['version_id']):
        ops.fail('操作题版本不存在', 422)
    exam = Exam(owner_id=user.id, **values)
    db.add(exam); db.flush()
    return configuration(db, exam)


def edit(db, user, eid, body):
    exam = managed(db, user, eid)
    if exam.status != 'draft' or exam.revision != body.revision:
        ops.fail('考试已发布或被修改，请重新读取；已发布配置需复制为新考试')
    values = draft_values(body)
    if values['version_id'] is not None and not db.get(OperationVersion, values['version_id']):
        ops.fail('操作题版本不存在', 422)
    for key, value in values.items():
        setattr(exam, key, value)
    exam.revision += 1
    db.flush()
    return configuration(db, exam)


def publish(db, user, eid, revision):
    exam = managed(db, user, eid)
    if exam.status == 'published' and exam.revision == revision + 1:
        return configuration(db, exam)
    if exam.status != 'draft' or exam.revision != revision:
        ops.fail('考试配置已变化，请重新读取')
    if not all((exam.name, exam.classes, exam.opens_at, exam.closes_at, exam.duration_minutes)):
        ops.fail('发布需要考试名称、题目版本、目标班级、开放及截止时间和正数答题时长')
    if exam.opens_at >= exam.closes_at or exam.closes_at <= now():
        ops.fail('开放时间必须早于截止时间，截止时间必须晚于当前时间')
    q, v = validate_version(db, exam.version_id)
    students = list(db.scalars(select(User).where(User.role == 'student', User.is_active.is_(True), User.class_name.in_(exam.classes))))
    if any(not any(u.class_name == name for u in students) for name in exam.classes):
        ops.fail('每个目标班级均须包含现有启用学生，请刷新班级名单')
    exam.question_snapshot = ops.detail(q, v)
    for student in students:
        db.add(ExamParticipant(exam_id=eid, student_id=student.id, identity_snapshot={
            'real_name': student.real_name, 'student_id': student.student_id, 'class_name': student.class_name}))
    exam.status = 'published'; exam.revision += 1
    exam.published_at = now(); exam.publisher_id = user.id
    db.flush()
    return configuration(db, exam)


def withdraw(db, user, eid, revision):
    exam = managed(db, user, eid)
    if exam.status != 'published' or exam.revision != revision:
        ops.fail('考试状态已变化，请重新读取')
    if db.scalar(select(ExamAttempt.session_id).where(ExamAttempt.exam_id == eid).limit(1)):
        ops.fail('已有学生开始考试，不得撤回、删除或重置机会')
    db.query(ExamParticipant).filter_by(exam_id=eid).delete(synchronize_session=False)
    exam.status = 'draft'; exam.revision += 1
    exam.question_snapshot = None; exam.published_at = None; exam.publisher_id = None
    db.flush()
    return configuration(db, exam)


def clone(db, user, eid):
    original = managed(db, user, eid)
    exam = Exam(owner_id=user.id, name=((original.name or '') + '（副本）')[:200],
                classes=deepcopy(original.classes), version_id=original.version_id,
                opens_at=original.opens_at, closes_at=original.closes_at, duration_minutes=original.duration_minutes)
    db.add(exam); db.flush()
    return configuration(db, exam)


def seal(db, attempt, reason, at):
    if attempt.submitted_at is not None:
        return
    record = db.get(OperationSession, attempt.session_id)
    record.status = 'submitted'
    attempt.submitted_at = at; attempt.finish_reason = reason; attempt.revision += 1
    db.flush()


def settle(db, attempt, at):
    if attempt.submitted_at is not None:
        return
    due = [(attempt.deadline, 'deadline')]
    if attempt.fullscreen_state == 'outside' and attempt.exited_at:
        due.append((attempt.exited_at + timedelta(seconds=60), 'fullscreen_timeout'))
    deadline, reason = min(due, key=lambda x: (x[0], x[1]))
    if at >= deadline:
        seal(db, attempt, reason, deadline)


def settle_all(db):
    with atomic(db):
        at = now()
        for attempt in db.scalars(select(ExamAttempt).where(ExamAttempt.submitted_at.is_(None))):
            settle(db, attempt, at)


def summary(db, attempt):
    exam = db.get(Exam, attempt.exam_id)
    return {'session_id': attempt.session_id, 'exam_id': exam.id, 'name': exam.name,
            'status': 'submitted' if attempt.submitted_at is not None else 'active',
            'started_at': iso(attempt.started_at), 'deadline': iso(attempt.deadline),
            'submitted_at': iso(attempt.submitted_at), 'finish_reason': attempt.finish_reason,
            'finish_reason_text': REASONS.get(attempt.finish_reason), 'exit_count': attempt.exit_count,
            'fullscreen_state': attempt.fullscreen_state, 'exited_at': iso(attempt.exited_at),
            'restore_deadline': iso(attempt.exited_at + timedelta(seconds=60)) if attempt.fullscreen_state == 'outside' and attempt.exited_at else None,
            'revision': attempt.revision, 'message': COMPLETED if attempt.submitted_at is not None else None,
            'server_now': iso(now())}


def detail(db, user, attempt, *, refresh=False):
    exam = db.get(Exam, attempt.exam_id)
    question = deepcopy(exam.question_snapshot)
    if user.role == 'student':
        # Explicit allowlist: no answer/session ID, even after submission.
        question = {key: question[key] for key in ('title', 'prompt', 'number', 'initial', 'station_version')}
    record = db.get(OperationSession, attempt.session_id)
    if refresh and user.role == 'student' and attempt.submitted_at is None:
        console = ops.refresh(db, user, attempt.session_id, exam=True, commit=False)
    else:
        if record.station_version != ops.station_version():
            console = None
        else:
            engine, session = unpack(ops.reference_station_package(), record.engine_state)
            console = ops.response(db, record, engine, session)
    participant = db.get(ExamParticipant, (exam.id, attempt.student_id))
    result = {**summary(db, attempt), 'question': question, 'opens_at': iso(exam.opens_at),
              'closes_at': iso(exam.closes_at), 'duration_minutes': exam.duration_minutes,
              'identity': participant.identity_snapshot, 'console': console}
    if user.role != 'student':
        result['control_events'] = [row.content for row in db.scalars(select(ExamControlEvent).where(
            ExamControlEvent.session_id == attempt.session_id).order_by(ExamControlEvent.id))]
        result['automatic_evaluation'] = None
    return result


def begin(db, user, eid, fullscreen):
    if not fullscreen:
        ops.fail('请先允许浏览器全屏；尚未创建正式答卷', 422)
    exam = db.get(Exam, eid)
    if not exam or exam.status != 'published' or not db.get(ExamParticipant, (eid, user.id)):
        ops.fail('考试不存在或不在本场考试名单中', 404)
    current = db.scalar(select(ExamAttempt).where(ExamAttempt.exam_id == eid, ExamAttempt.student_id == user.id))
    at = now()
    if current:
        settle(db, current, at)
        return detail(db, user, current)
    if at < exam.opens_at or at >= exam.closes_at:
        ops.fail('考试尚未开放或已经截止')
    frozen = exam.question_snapshot
    if frozen['station_version'] != ops.station_version():
        ops.fail('考试标准站版本与当前程序不同，请联系教师；未占用作答机会')
    engine = ops.ReferenceSimulationService(ops.reference_station_package())
    initial = deepcopy(frozen['initial'])
    snapshot = engine.new_session(user.id, initial.get('interval_available', True), initial.get('occupied_sections', []))
    sid = snapshot['session_id']
    db.add(OperationSession(id=sid, owner_id=user.id, version_id=exam.version_id, kind='exam',
        engine_state=ops.persistent_state(engine, sid), initial_snapshot=initial, station_version=frozen['station_version']))
    db.flush()
    attempt = ExamAttempt(session_id=sid, exam_id=eid, student_id=user.id, started_at=at,
        deadline=min(at + timedelta(minutes=exam.duration_minutes), exam.closes_at))
    db.add(attempt); db.flush()
    return detail(db, user, attempt)


def control(db, attempt, event, received_at):
    clean = event.model_dump(mode='json')
    fingerprint = ops.digest(clean)
    old = db.scalar(select(ExamControlEvent).where(ExamControlEvent.session_id == attempt.session_id,
                                                  ExamControlEvent.event_id == str(event.event_id)))
    if old:
        if old.fingerprint != fingerprint:
            ops.fail('同一全屏事件ID不得更换内容')
        return
    at = utc(event.occurred_at)
    if at > received_at + timedelta(seconds=5) or at < attempt.started_at - timedelta(seconds=5):
        ops.fail('全屏事件时间超出答卷范围，请保留待同步记录并校准系统时间', 422)
    at = max(attempt.started_at, min(at, received_at))
    applied = False
    if attempt.last_control_at is None or at >= attempt.last_control_at:
        settle(db, attempt, at)
        if attempt.submitted_at is None:
            if event.kind == 'exit' and attempt.fullscreen_state == 'inside':
                attempt.fullscreen_state = 'outside'; attempt.exited_at = at
                attempt.exit_count += 1; applied = True
                if attempt.exit_count >= 2:
                    seal(db, attempt, 'fullscreen_limit', at)
            elif event.kind == 'restore' and attempt.fullscreen_state == 'outside':
                attempt.fullscreen_state = 'inside'; applied = True
            attempt.last_control_at = at
            attempt.revision += 1
    db.add(ExamControlEvent(session_id=attempt.session_id, event_id=str(event.event_id), fingerprint=fingerprint,
        content={**clean, 'received_at': iso(received_at), 'effective_at': iso(at), 'applied': applied}))
    db.flush()


def sync(db, user, sid, body):
    attempt = owned(db, user, sid)
    received = now()
    for event in body.events:
        control(db, attempt, event, received)
    settle(db, attempt, received)
    # A refreshed/new client must report actual fullscreen even without a local queue.
    expected = 'inside' if body.fullscreen else 'outside'
    if attempt.submitted_at is None and attempt.fullscreen_state != expected:
        from app.schemas.exam import ControlEvent
        control(db, attempt, ControlEvent(event_id=uuid4(), kind='restore' if body.fullscreen else 'exit',
                                         occurred_at=received.replace(tzinfo=timezone.utc)), received)
    settle(db, attempt, received)
    output = detail(db, user, attempt, refresh=True)
    output['acknowledged_events'] = [str(event.event_id) for event in body.events]
    return output


def click(db, user, sid, body):
    attempt = owned(db, user, sid)
    settle(db, attempt, now())
    previous = db.scalar(select(OperationEvent).where(OperationEvent.session_id == sid,
                                                     OperationEvent.event_id == str(body.event_id)))
    if not previous and (attempt.submitted_at is not None or attempt.fullscreen_state != 'inside'):
        # Preserve deadline settlement even though the late action itself is rejected.
        db.commit()
        ops.fail('考试已结束或尚未恢复全屏，不能追加操作')
    return ops.click(db, user, sid, body, exam=True, commit=False)


def submit(db, user, sid, expected_sequence):
    attempt = owned(db, user, sid)
    settle(db, attempt, now())
    if attempt.submitted_at is None:
        if db.get(OperationSession, sid).revision != expected_sequence:
            ops.fail('操作记录尚未同步，请同步确认日志后再提交')
        seal(db, attempt, 'manual', now())
    return detail(db, user, attempt)


def get_detail(db, user, sid):
    attempt = owned(db, user, sid)
    settle(db, attempt, now())
    return detail(db, user, attempt)


def list_exams(db, user, number):
    if user.role != 'student':
        statement = select(Exam).order_by(Exam.id.desc())
        if user.role == 'teacher':
            statement = statement.where(Exam.owner_id == user.id)
        return page([configuration(db, exam) for exam in db.scalars(statement)], number)
    rows = []
    for exam in db.scalars(select(Exam).join(ExamParticipant).where(ExamParticipant.student_id == user.id,
                Exam.status == 'published').order_by(Exam.opens_at.desc(), Exam.id.desc())):
        attempt = db.scalar(select(ExamAttempt).where(ExamAttempt.exam_id == exam.id, ExamAttempt.student_id == user.id))
        if attempt:
            settle(db, attempt, now())
        state = ('submitted' if attempt.submitted_at is not None else 'active') if attempt else (
            'upcoming' if now() < exam.opens_at else 'missed' if now() >= exam.closes_at else 'open')
        row = {'id': exam.id, 'name': exam.name, 'opens_at': iso(exam.opens_at), 'closes_at': iso(exam.closes_at),
               'duration_minutes': exam.duration_minutes, 'state': state,
               'attempt': summary(db, attempt) if attempt else None}
        rows.append(row)
    priority = {'active': 0, 'open': 1, 'upcoming': 2, 'missed': 3, 'submitted': 3}
    rows.sort(key=lambda row: (priority[row['state']], datetime.fromisoformat(row['opens_at']).timestamp()
                              * (1 if row['state'] == 'upcoming' else -1), -row['id']))
    return {**page(rows, number), 'server_now': iso(now())}


def history(db, user, number, eid=None):
    statement = select(ExamAttempt).order_by(ExamAttempt.started_at.desc(), ExamAttempt.session_id.desc())
    if user.role == 'student':
        statement = statement.where(ExamAttempt.student_id == user.id)
    else:
        managed(db, user, eid)
        statement = statement.where(ExamAttempt.exam_id == eid)
    rows = []
    for attempt in db.scalars(statement):
        settle(db, attempt, now())
        if user.role != 'student' or attempt.submitted_at is not None:
            item = summary(db, attempt)
            if user.role != 'student':
                item['identity'] = db.get(ExamParticipant, (attempt.exam_id, attempt.student_id)).identity_snapshot
            rows.append(item)
    return page(rows, number)


def download(db, user, sid):
    attempt = owned(db, user, sid)
    settle(db, attempt, now())
    if user.role == 'student' and attempt.submitted_at is None:
        ops.fail('交卷后才能下载本人日志')
    result = detail(db, user, attempt)
    record = db.get(OperationSession, sid)
    # Download has the same allowlist/permissions as detail. Never include a raw model.
    return {**result, 'schema_version': 1, 'kind': 'exam', 'events': ops.events(db, sid),
            'runtime_events': record.engine_state.get('runtime_events', []), 'station_version': record.station_version}
