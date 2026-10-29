"""Learning endpoints, deliberately distinct from authoring and theory grading."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import require_roles
from app.api.operations import json_download
from app.core.database import get_db
from app.models.user import User
from app.schemas.operation import Click, Body
from app.schemas.operation_learning import Begin, Review
from app.services import operation_learning as service, operations as ops, operation_explanation

router = APIRouter()
student = require_roles('student')
reader = require_roles('student', 'teacher', 'admin')
manager = require_roles('teacher', 'admin')


@router.get('/station')
def station(user: User = Depends(student)):
    return ops.reference_station_package()


@router.post('/questions/{qid}/begin')
def begin(qid: int, body: Begin, db: Session = Depends(get_db), user: User = Depends(student)):
    with ops.LOCK:
        return service.begin(db, user, qid, body.restart_from)


@router.get('/attempts')
def attempts(page: int = Query(1, ge=1), question_id: int | None = Query(None, ge=1),
             class_name: str = Query('', max_length=100), student_number: str = Query('', max_length=100),
             question_search: str = Query('', max_length=200),
             db: Session = Depends(get_db), user: User = Depends(reader)):
    return service.list_attempts(db, user, page, class_name, student_number, question_id, question_search)


@router.get('/attempts/{sid}')
def detail(sid: str, db: Session = Depends(get_db), user: User = Depends(reader)):
    with ops.LOCK:
        return service.detail(db, user, sid)


@router.post('/attempts/{sid}/events')
def click(sid: str, body: Click, db: Session = Depends(get_db), user: User = Depends(student)):
    with ops.LOCK:
        service.owned(db, user, sid)
        return ops.click(db, user, sid, body)


@router.get('/attempts/{sid}/console')
def console(sid: str, db: Session = Depends(get_db), user: User = Depends(student)):
    with ops.LOCK:
        service.owned(db, user, sid)
        return ops.refresh(db, user, sid)


@router.post('/attempts/{sid}/submit')
def submit(sid: str, body: Body, db: Session = Depends(get_db), user: User = Depends(student)):
    with ops.LOCK:
        return service.submit(db, user, sid)


@router.post('/attempts/{sid}/explanation')
def explanation(sid: str, body: Body, db: Session = Depends(get_db), user: User = Depends(reader)):
    return operation_explanation.explain(db, user, sid)


@router.put('/attempts/{sid}/review')
def review(sid: str, body: Review, db: Session = Depends(get_db), user: User = Depends(manager)):
    with ops.LOCK:
        return service.save_review(db, user, sid, body)


@router.get('/attempts/{sid}/log.json')
def download(sid: str, db: Session = Depends(get_db), user: User = Depends(reader)):
    return json_download(service.download(db, user, sid), f'learning-{sid}.json')
