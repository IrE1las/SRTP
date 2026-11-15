"""Current-account learning evidence, without changing original grading."""
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session, defer, load_only
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.lab_topic import LabAttempt
from app.models.exercise import Exercise
from app.models.exercise_session import ExerciseSession
from app.models.operation_log import OperationLog
from app.models.ai_score import AiScore

router = APIRouter()
Kind = Literal['lab', 'legacy']
LABELS = {'lab':'实验专题', 'legacy':'教学练习'}
STATUSES = {'in_progress': '进行中', 'ongoing': '进行中', 'submitted': '已提交',
            'recorded': '已记录', 'pending_review': '待教师评阅', 'graded': '已评分',
            'completed': '已完成', 'finished': '已结束', 'timeout': '已超时', 'abandoned': '已结束'}


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
        f"/student/lab-topics?q={quote(question.get('key', ''))}", operations, errors, score,
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


def own_records(db, user, kind='all'):
    records=[]
    if kind in {'all','lab'}:
        attempts=db.query(LabAttempt).filter_by(student_id=user.id).filter(
            LabAttempt.question_snapshot['topic'].as_integer().between(1,6))
        records += [lab_view(db,a,user) for a in attempts]
    if kind in {'all','legacy'}:
        records += [legacy_view(db,a,user) for a in db.query(ExerciseSession).filter_by(student_id=user.id)]
    return records


@router.get('')
def list_records(kind: Literal['all','lab','legacy'] = 'all',
                 page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = own_records(db, user)
    counts = {key: sum(item['kind'] == key for item, _ in records) for key in LABELS}
    counts['all'] = len(records)
    items = [item for item, _ in records if kind == 'all' or item['kind'] == kind]
    items.sort(key=lambda item: (item['updated_at'].isoformat(), item['key']), reverse=True)
    return {'items': items[(page - 1) * limit:page * limit], 'total': len(items), 'counts': counts}


@router.get('/{kind}/{record_id}')
def record_detail(kind: str, record_id: str, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    models={'lab':(LabAttempt,'student_id'),'legacy':(ExerciseSession,'student_id')}
    if kind not in models or not record_id.isdigit():
        raise HTTPException(404,'学习记录不存在')
    model,owner=models[kind]
    attempt=db.query(model).filter(model.id==int(record_id),getattr(model,owner)==user.id).first()
    if attempt is None or (kind=='lab' and attempt.question_snapshot.get('topic') in (7,8)):
        raise HTTPException(404,'学习记录不存在')
    item,detail=lab_view(db,attempt,user) if kind=='lab' else legacy_view(db,attempt,user)
    return {**item,**detail}
