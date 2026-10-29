from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_roles
from app.api.operations import json_download
from app.core.database import get_db
from app.models import User
from app.models.exam import Exam, ExamParticipant
from app.models.operation import OperationQuestion, OperationVersion
from app.schemas.exam import ExamDraft, ExamEdit, Revision, Begin, Sync, Submit
from app.schemas.operation import Click
from app.services import exams as service, operations as ops

router = APIRouter()
manager = require_roles('teacher', 'admin')
student = require_roles('student')


def transaction(db, function, *args, **kwargs):
    with ops.LOCK, service.atomic(db):
        return function(db, *args, **kwargs)


@router.get('')
def listing(page: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return transaction(db, service.list_exams, user, page)


@router.get('/versions')
def versions(page: int = Query(1, ge=1), search: str = Query('', max_length=200),
             db: Session = Depends(get_db), user: User = Depends(manager)):
    rows = []
    for v in db.scalars(select(OperationVersion).join(OperationQuestion).where(
        OperationVersion.status == 'published', OperationQuestion.disabled.is_(False)).order_by(OperationVersion.id.desc())):
        if search.strip().casefold() in (v.title or '').casefold():
            rows.append({'version_id': v.id, 'question_id': v.question_id, 'number': v.number, 'title': v.title})
    return service.page(rows, page)


@router.get('/station')
def station(user: User = Depends(get_current_user)):
    return ops.reference_station_package()


@router.get('/history')
def history(page: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(student)):
    return transaction(db, service.history, user, page)


@router.post('')
def create(body: ExamDraft, db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, service.create, user, body)


@router.get('/{eid:int}')
def configuration(eid: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    return service.configuration(db, service.managed(db, user, eid))


@router.put('/{eid:int}')
def edit(eid: int, body: ExamEdit, db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, service.edit, user, eid, body)


@router.post('/{eid:int}/publish')
def publish(eid: int, body: Revision, db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, service.publish, user, eid, body.revision)


@router.post('/{eid:int}/withdraw')
def withdraw(eid: int, body: Revision, db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, service.withdraw, user, eid, body.revision)


@router.post('/{eid:int}/copy')
def clone(eid: int, db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, service.clone, user, eid)


@router.get('/{eid:int}/participants')
def participants(eid: int, page: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(manager)):
    service.managed(db, user, eid)
    rows = [{'student_id': row.student_id, **row.identity_snapshot} for row in db.scalars(select(ExamParticipant).where(
        ExamParticipant.exam_id == eid).order_by(ExamParticipant.student_id))]
    rows.sort(key=lambda row: (row.get('class_name') or '', row.get('student_id') or ''))
    return service.page(rows, page)


@router.get('/{eid:int}/attempts')
def attempts(eid: int, page: int = Query(1, ge=1), db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, service.history, user, page, eid)


@router.post('/{eid:int}/begin')
def begin(eid: int, body: Begin, db: Session = Depends(get_db), user: User = Depends(student)):
    return transaction(db, service.begin, user, eid, body.fullscreen)


@router.get('/attempts/{sid}')
def detail(sid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return transaction(db, service.get_detail, user, sid)


@router.post('/attempts/{sid}/sync')
def sync(sid: str, body: Sync, db: Session = Depends(get_db), user: User = Depends(student)):
    return transaction(db, service.sync, user, sid, body)


@router.post('/attempts/{sid}/events')
def click(sid: str, body: Click, db: Session = Depends(get_db), user: User = Depends(student)):
    return transaction(db, service.click, user, sid, body)


@router.post('/attempts/{sid}/submit')
def submit(sid: str, body: Submit, db: Session = Depends(get_db), user: User = Depends(student)):
    return transaction(db, service.submit, user, sid, body.expected_sequence)


@router.get('/attempts/{sid}/log.json')
def download(sid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return json_download(transaction(db, service.download, user, sid), 'exam-log.json')
