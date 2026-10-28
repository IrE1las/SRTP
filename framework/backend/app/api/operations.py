"""S3 endpoints. Role and ownership checks apply to every record and download."""
import json
from typing import Literal
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.user import User
from app.models.operation import OperationQuestion, OperationVersion, OperationSession
from app.schemas.operation import Draft, UpdateDraft, StartSession, Click
from app.services import operations as service

router = APIRouter()
manager = require_roles('teacher', 'admin')
reader = require_roles('student', 'teacher', 'admin')


@router.get('/station')
def station(user: User = Depends(manager)):
    return service.reference_station_package()


@router.get('/classes')
def classes(db: Session = Depends(get_db), user: User = Depends(manager)):
    counts = {}
    for name in db.scalars(select(User.class_name).where(User.role == 'student', User.class_name.is_not(None))):
        name = name.strip()
        if name:
            counts[name] = counts.get(name, 0) + 1
    items = [{'name': name, 'student_count': count} for name, count in sorted(counts.items())]
    return {'items': items, 'total': len(items)}


@router.get('/questions')
def questions(page: int = Query(default=1, ge=1), search: str = Query(default='', max_length=200),
              status: Literal['all', 'draft', 'published', 'disabled'] = 'all',
              db: Session = Depends(get_db), user: User = Depends(reader)):
    return service.list_questions(db, user, page, search, status)


@router.post('/questions')
def create(body: Draft, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.create(db, user, body)


@router.get('/questions/{qid}')
def question(qid: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    q = service.question(db, user, qid)
    result = service.detail(q, service.latest(db, qid))
    result['versions'] = [{'id': v.id, 'number': v.number, 'status': v.status} for v in db.scalars(
        select(OperationVersion).where(OperationVersion.question_id == qid).order_by(OperationVersion.number))]
    result['sessions'] = [{'id': s.id, 'kind': s.kind, 'status': s.status, 'version_id': s.version_id,
                           'owner_id': s.owner_id} for s in db.scalars(select(OperationSession).join(
        OperationVersion, OperationSession.version_id == OperationVersion.id).where(
            OperationVersion.question_id == qid).order_by(OperationSession.created_at.desc()))]
    return result


@router.delete('/questions/{qid}')
def delete_question(qid: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.delete_question(db, user, qid)


@router.put('/questions/{qid}')
def edit(qid: int, body: UpdateDraft, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.edit(db, user, qid, body)


@router.post('/questions/{qid}/publish')
def publish(qid: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.publish(db, user, qid)


@router.post('/questions/{qid}/disable')
def disable(qid: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        q = service.question(db, user, qid)
        q.disabled = True
        db.commit()
        return service.detail(q, service.latest(db, qid))


@router.get('/questions/{qid}/versions/{number}')
def version(qid: int, number: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    q = service.question(db, user, qid)
    v = db.scalar(select(OperationVersion).where(OperationVersion.question_id == qid, OperationVersion.number == number))
    if not v:
        service.fail('版本不存在', 404)
    return service.detail(q, v)


@router.get('/questions/{qid}/standard.json')
def standard(qid: int, number: int | None = None, db: Session = Depends(get_db), user: User = Depends(manager)):
    service.question(db, user, qid)
    v = service.latest(db, qid) if number is None else db.scalar(select(OperationVersion).where(
        OperationVersion.question_id == qid, OperationVersion.number == number))
    if not v or not v.standard_session_id:
        service.fail('该版本尚无保存的标准日志', 404)
    return json_download(service.download(db, user, v.standard_session_id), f'question-{qid}-v{v.number}.json')


@router.post('/questions/{qid}/sessions')
def start(qid: int, body: StartSession, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.start_session(db, user, qid, body.kind)


@router.get('/sessions/{sid}')
def session(sid: str, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.view_session(db, user, sid)


@router.post('/sessions/{sid}/events')
def click(sid: str, body: Click, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.click(db, user, sid, body)


@router.post('/sessions/{sid}/stop')
def stop(sid: str, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.stop(db, user, sid)


@router.post('/sessions/{sid}/save-standard')
def save(sid: str, db: Session = Depends(get_db), user: User = Depends(manager)):
    with service.LOCK:
        return service.save_standard(db, user, sid)


def json_download(content, filename):
    return Response(json.dumps(content, ensure_ascii=False, indent=2).encode('utf-8'),
        media_type='application/json; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.get('/sessions/{sid}/log.json')
def log(sid: str, db: Session = Depends(get_db), user: User = Depends(manager)):
    return json_download(service.download(db, user, sid), 'operation-log.json')
