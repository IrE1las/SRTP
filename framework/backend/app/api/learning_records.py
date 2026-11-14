"""Current-account learning evidence, without changing original grading."""
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session, defer, load_only
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.module_one import ModuleOneAttempt, ModuleOneEvent
from app.models.lab_topic import LabAttempt
from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.models.operation_log import OperationLog
from app.models.ai_score import AiScore
from app.models.learning_archive import LearningArchive, LearningArchiveEvent

router = APIRouter()
Kind = Literal['dynamic', 'lab', 'simulation', 'classic', 'legacy']
LABELS = {'dynamic': '动态实验', 'lab': '实验专题', 'simulation': '自由仿真', 'classic': '经典图形专项', 'legacy': '教学练习'}
STATUSES = {'in_progress': '进行中', 'ongoing': '进行中', 'submitted': '已提交',
            'recorded': '已记录', 'pending_review': '待教师评阅', 'graded': '已评分',
            'completed': '已完成', 'finished': '已结束', 'timeout': '已超时', 'abandoned': '已结束'}
CLASSIC_PATHS = {'dongjiao_to_III': '/student/interlocking-exam', 'dongjiao_to_I': '/student/interlocking-exam-protective',
                 'dongjiao_to_4': '/student/interlocking-exam-driven', 'beijing_depart_5': '/student/interlocking-exam-conditional'}


def error(label, message, correction='', devices=None, operation_id=None):
    return dict(label=label, message=message, correction=correction, devices=devices or [], operation_id=operation_id)


def feedback(source, title, text, time):
    return dict(source=source, title=title, text=text, time=time)


def operation(oid, sequence, time, action, target, accepted, message):
    return dict(id=str(oid), sequence=sequence, time=time, action=action, target=target,
                accepted=accepted, message=message)


def base(kind, record_id, title, status, started, updated, preview, path, operations, errors, score=None,
         score_max=None, score_label=None, operation_count=None, error_count=None):
    return dict(key=f'{kind}:{record_id}', record_id=str(record_id), kind=kind, kind_label=LABELS[kind],
        title=title, status=status, status_label=STATUSES.get(status, status), started_at=started, updated_at=updated,
        operation_count=len(operations) if operation_count is None else operation_count,
        error_count=len(errors) if error_count is None else error_count, score=score, score_max=score_max,
        score_label=score_label or (f'{score:g} / {score_max:g}' if score is not None and score_max is not None else '未评分'),
        preview=preview, continue_path=path)


def dynamic_view(db, attempt, detailed=True):
    events = (db.query(ModuleOneEvent).filter_by(attempt_id=attempt.id).order_by(ModuleOneEvent.after_version).all()
              if detailed else [])
    event_count, last_event = (len(events), events[-1].created_at if events else None) if detailed else db.query(
        func.count(ModuleOneEvent.id), func.max(ModuleOneEvent.created_at)).filter_by(attempt_id=attempt.id).one()
    operations = [operation(e.id, e.after_version, e.created_at, e.command.get('type', ''),
        e.command.get('target', ''), e.response.get('accepted'), e.response.get('message', '')) for e in events]
    # Do not derive errors from refusals: several experiments require a refusal.
    # Until submission neither checkpoints nor inferred grading evidence is exposed.
    result = attempt.result if attempt.status == 'submitted' else None
    errors = [error(c['label'], c.get('message', ''), c.get('correction', ''), c.get('devices'), c.get('event_id'))
              for c in (result or {}).get('checkpoints', []) if not c.get('passed')]
    updates = attempt.submitted_at or last_event or attempt.started_at
    score = (result or {}).get('score')
    item = base('dynamic', attempt.id, attempt.question_snapshot.get('title', attempt.question_id), attempt.status,
        attempt.started_at, updates, attempt.preview,
        f'/student/modules/one/experiment-1/{quote(attempt.question_id)}?attempt={attempt.id}', operations, errors,
        score, 100 if score is not None else None, operation_count=event_count)
    if not detailed:
        return item, {}
    messages = [feedback('rules', '操作反馈', e.response['message'], e.created_at) for e in events if e.response.get('message')]
    detail = dict(operations=operations, errors=errors, feedback=messages,
        snapshots={'initial': attempt.initial_snapshot, 'latest': events[-1].response.get('snapshot') if events else attempt.initial_snapshot})
    if result:
        detail['assessment'] = result
    if attempt.notes:
        detail['notes'] = attempt.notes
    return item, detail


def lab_view(db, attempt, user):
    result, review, question = attempt.result, attempt.review or {}, attempt.question_snapshot
    fields = {f['id']: f for f in question.get('fields', [])}
    operations = [operation(fid, i, attempt.created_at, '提交作答', fields.get(fid, {}).get('label', fid),
                            None, str(answer)) for i, (fid, answer) in enumerate(attempt.answers.items(), 1)]
    errors, messages = [], []
    for f in result.get('feedback', []):
        if f.get('status') in {'incorrect', 'partial'}:
            errors.append(error(f.get('label', ''), '；'.join(f.get('errors', [])) or '答案未完全符合要求',
                f.get('explanation', ''), operation_id=f.get('id')))
        if f.get('explanation') or f.get('message'):
            messages.append(feedback('rules', f.get('label', '作答反馈'), f.get('explanation') or f['message'], attempt.created_at))
    if review.get('comment'):
        messages.append(feedback('teacher', '教师评语', review['comment'], attempt.reviewed_at))
    for fid, comment in review.get('field_comments', {}).items():
        messages.append(feedback('teacher', fields.get(fid, {}).get('label', fid), comment, attempt.reviewed_at))
    score = review.get('total_score', result.get('total_score'))
    status = 'graded' if attempt.review else result.get('status', 'submitted')
    label = None if score is not None else f"客观项 {result.get('automatic_score', 0):g} / {result.get('automatic_max', 0):g}，总分待教师评阅"
    item = base('lab', attempt.id, question.get('title', '实验专题作答'), status, attempt.created_at,
        attempt.reviewed_at or attempt.created_at, user.role != 'student',
        f"/student/lab-topics?view=reports&q={quote(question.get('key', ''))}", operations, errors, score,
        result.get('total_max'), label)
    return item, dict(operations=operations, errors=errors, feedback=messages, answers=attempt.answers,
                      assessment=result, review=attempt.review)


def legacy_view(db, attempt, user):
    exercise = db.get(Exercise, attempt.exercise_id)
    logs = db.query(OperationLog).options(load_only(OperationLog.id, OperationLog.sequence_no,
        OperationLog.timestamp, OperationLog.operation_type, OperationLog.target_code,
        OperationLog.operation_result, OperationLog.error_message)).filter_by(session_id=attempt.id).order_by(OperationLog.sequence_no).all()
    operations = [operation(e.id, e.sequence_no, e.timestamp, e.operation_type, e.target_code,
                            e.operation_result == 'success', e.error_message or '') for e in logs]
    errors = [error('操作未成功', e.error_message or '操作未成功', devices=[e.target_code], operation_id=str(e.id))
              for e in logs if e.operation_result != 'success']
    score = db.query(AiScore).filter_by(session_id=attempt.id).first() if attempt.status != 'ongoing' else None
    messages = []
    if score:
        # Current scorer is local even with a configured key (deepseek_placeholder).
        mode = score.deepseek_response.get('mode')
        source = 'rules_fallback' if mode in {'local_fallback', 'deepseek_placeholder'} else 'ai' if mode in {'ai', 'deepseek'} else 'rules'
        messages.append(feedback(source, '练习评分反馈', score.ai_comment, score.created_at))
        messages += [feedback(source, '改进建议', s, score.created_at) for s in score.suggestions]
    item = base('legacy', attempt.id, exercise.title if exercise else '教学练习', attempt.status, attempt.start_time,
        attempt.end_time or (logs[-1].timestamp if logs else attempt.start_time), user.role != 'student',
        f'/student/history/{attempt.id}', operations, errors, score.total_score if score else None, 100 if score else None)
    return item, dict(operations=operations, errors=errors, feedback=messages,
                      snapshots={'latest': attempt.final_snapshot})


def classic_errors(comparison):
    errors = []
    names = {'route_buttons': '进路按钮', 'switches': '道岔', 'hostile_signals': '敌对信号', 'track_sections': '轨道区段'}
    for category, differences in comparison.get('details', {}).get('errors', {}).items():
        for problem, values in differences.items():
            if problem == 'correct' or not values:
                continue
            for value in values:
                device = value.get('switch', '') if isinstance(value, dict) else str(value)
                label = {'missing': '漏选', 'extra': '多选', 'wrong_position': '位置错误'}.get(problem, problem)
                correction = (f"应为{'定位' if value['expected'] == 'normal' else '反位'}" if isinstance(value, dict)
                              else '请结合联锁表核对本项设备。')
                errors.append(error(names.get(category, category) + label, device, correction, [device]))
    return errors


def archive_view(db, archive, detailed=True):
    events = (db.query(LearningArchiveEvent).filter_by(archive_id=archive.id).order_by(LearningArchiveEvent.sequence).all()
              if detailed and archive.kind == 'simulation' else [])
    operations = [operation(e.id, e.sequence, e.created_at, e.command.get('type', ''), e.command.get('target', ''),
                            e.response.get('accepted'), e.response.get('message', '')) for e in events]
    messages = list(archive.feedback) if detailed else []
    if archive.kind == 'simulation':
        event_count, rejection_count = (len(events), sum(e.response.get('accepted') is False for e in events)) if detailed else db.query(
            func.count(LearningArchiveEvent.id),
            func.coalesce(func.sum(case((LearningArchiveEvent.response['accepted'].as_boolean().is_(False), 1), else_=0)), 0)
        ).filter_by(archive_id=archive.id).one()
        errors = [error('命令被拒绝', e.response.get('message', ''), devices=e.response.get('devices', []), operation_id=e.id)
                  for e in events if e.response.get('accepted') is False]
        messages += [feedback('rules', '操作台规则反馈', e.response['message'], e.created_at) for e in events if e.response.get('message')]
        path, label = '/student/simulation-console', '未评分（自由仿真无正式评分标准）'
        detail = {'snapshots': {'initial': archive.initial_snapshot, 'latest': archive.latest_snapshot,
            'frames': [{'operation_id': e.id, 'before': e.before_snapshot, 'after': e.response.get('snapshot')} for e in events]},
            'partial_history': archive.data.get('partial_history', False)} if detailed else {}
    else:
        comparison, answer = archive.data.get('comparison', {}), archive.data.get('answer', {})
        errors = classic_errors(comparison)
        operations = [operation(archive.id, 1, archive.started_at, '提交图形答案', archive.title, None, comparison.get('message', ''))]
        messages.insert(0, feedback('rules', '本地答案核对', comparison.get('message', ''), archive.started_at))
        path = CLASSIC_PATHS.get(answer.get('route_type'), CLASSIC_PATHS['dongjiao_to_III'])
        label = '核对通过（未设数值评分）' if comparison.get('all_correct') else '存在差异（未设数值评分）'
        detail = {'answers': answer, 'assessment': comparison}
        event_count, rejection_count = len(operations), len(errors)
    item = base(archive.kind, archive.id, archive.title, archive.status, archive.started_at, archive.updated_at,
                archive.preview, path, operations, errors, score_label=label,
                operation_count=event_count, error_count=rejection_count)
    return item, dict(**detail, operations=operations, errors=errors, feedback=messages)


def own_records(db, user, kind='all'):
    records = []
    if kind in {'all', 'dynamic'}:
        query = db.query(ModuleOneAttempt).options(defer(ModuleOneAttempt.state), defer(ModuleOneAttempt.initial_snapshot))
        records += [dynamic_view(db, a, detailed=False) for a in query.filter_by(owner_id=user.id)]
    if kind in {'all', 'lab'}:
        records += [lab_view(db, a, user) for a in db.query(LabAttempt).filter_by(student_id=user.id)]
    if kind in {'all', 'legacy'}:
        records += [legacy_view(db, a, user) for a in db.query(ExerciseSession).filter_by(student_id=user.id)]
    if kind in {'all', 'simulation', 'classic'}:
        query = db.query(LearningArchive).options(defer(LearningArchive.initial_snapshot),
            defer(LearningArchive.latest_snapshot), defer(LearningArchive.feedback)).filter_by(owner_id=user.id)
        if kind != 'all':
            query = query.filter_by(kind=kind)
        records += [archive_view(db, a, detailed=False) for a in query]
    return records


@router.get('')
def list_records(kind: Literal['all', 'dynamic', 'lab', 'simulation', 'classic', 'legacy'] = 'all',
                 page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = own_records(db, user)
    counts = {key: sum(item['kind'] == key for item, _ in records) for key in LABELS}
    counts['all'] = len(records)
    items = [item for item, _ in records if kind == 'all' or item['kind'] == kind]
    items.sort(key=lambda item: (item['updated_at'].isoformat(), item['key']), reverse=True)
    return {'items': items[(page - 1) * limit:page * limit], 'total': len(items), 'counts': counts}


@router.get('/{kind}/{record_id}')
def record_detail(kind: Kind, record_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    models = {'dynamic': (ModuleOneAttempt, 'owner_id'), 'lab': (LabAttempt, 'student_id'),
              'legacy': (ExerciseSession, 'student_id'), 'simulation': (LearningArchive, 'owner_id'),
              'classic': (LearningArchive, 'owner_id')}
    model, owner_key = models[kind]
    if kind in {'lab', 'legacy'} and not record_id.isdigit():
        raise HTTPException(404, '学习记录不存在')
    query = db.query(model).filter(model.id == record_id, getattr(model, owner_key) == user.id)
    if kind in {'simulation', 'classic'}:
        query = query.filter_by(kind=kind)
    attempt = query.first()
    if attempt is None:
        raise HTTPException(404, '学习记录不存在')
    if kind == 'dynamic':
        item, detail = dynamic_view(db, attempt)
    elif kind == 'lab':
        item, detail = lab_view(db, attempt, user)
    elif kind == 'legacy':
        item, detail = legacy_view(db, attempt, user)
    else:
        item, detail = archive_view(db, attempt)
    return {**item, **detail}
