from fastapi import APIRouter, Depends, Query
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_roles, bearer_scheme
from app.api.operations import json_download
from app.core.database import get_db
from app.models import User
from app.models.exam import Exam, ExamParticipant
from app.models.operation import OperationQuestion, OperationVersion
from app.schemas.exam import ExamDraft, ExamEdit, Revision, Begin, Sync, Submit
from app.schemas.operation import Click
from app.services import exams as service, operations as ops
from app.services import exam_grades as grades
from app.schemas.exam_grade import GradeDraft, GradeRevision
from app.services import exam_review_queue
from app.schemas.operation_assessment import AssessmentReview

router = APIRouter()
manager = require_roles('teacher', 'admin')
student = require_roles('student')


def exam_student(credentials=Depends(bearer_scheme), db: Session=Depends(get_db)):
    # Release authentication's connection in this worker, before awaiting an endpoint.
    # Student exam services only read this detached identity and never mutate User.
    user = get_current_user(credentials, db)
    if user.role != 'student':
        ops.fail('当前角色无权访问该资源', 403)
    db.expunge(user)
    db.rollback()
    return user


def transaction(db, function, *args, **kwargs):
    from app.services.simulation_console import clock
    with ops.LOCK, service.atomic(db), clock.at(service.now()):
        return function(db, *args, **kwargs)


@router.get('/attempts/{sid}/evidence')
def evidence_page(sid: str, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                  db: Session = Depends(get_db), user: User = Depends(manager)):
    from app.models.operation_assessment import OperationEvidenceEvent
    service.owned(db, user, sid)
    rows = list(db.scalars(select(OperationEvidenceEvent).where(OperationEvidenceEvent.session_id == sid,
        OperationEvidenceEvent.sequence > after).order_by(OperationEvidenceEvent.sequence).limit(limit)))
    return {'items': [{'sequence': r.sequence, **r.content} for r in rows],
            'next_cursor': rows[-1].sequence if rows else after}


@router.get('/attempts/{sid}/events')
def click_page(sid: str, after: int=Query(0,ge=0), limit:int=Query(50,ge=1,le=200),
               db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    from app.models.operation import OperationEvent
    attempt=service.owned(db,user,sid)
    if user.role=='student' and not attempt.submitted_at:
        ops.fail('交卷后才能分页查看本人操作日志')
    rows=list(db.scalars(select(OperationEvent).where(OperationEvent.session_id==sid,
        OperationEvent.sequence>after).order_by(OperationEvent.sequence).limit(limit)))
    return {'items':[r.content for r in rows],'next_cursor':rows[-1].sequence if rows else after}


@router.post('/attempts/{sid}/archive')
def export_archive(sid:str,db:Session=Depends(get_db),user:User=Depends(manager)):
    from app.services.operation_assessment.archive import export
    # Authorization and reads complete before compression; never delete online evidence.
    service.owned(db,user,sid)
    try:
        return export(db,user,sid)
    except ValueError as exc:
        ops.fail(str(exc),422)


@router.post('/attempts/{sid}/evaluate')
def evaluate(sid: str, db: Session = Depends(get_db), user: User = Depends(manager)):
    from app.services.operation_assessment import service as assessment
    def run(db):
        attempt = grades.reviewable(db, user, sid)
        return assessment.evaluate(db, attempt)
    return transaction(db, run)


@router.post('/attempts/{sid}/assessment-review')
def review_assessment(sid: str, body: AssessmentReview, db: Session = Depends(get_db), user: User = Depends(manager)):
    from app.models.exam_grade import ExamGrade
    from app.models.operation_assessment import ExamAssessmentReview, ExamAssessmentReviewHistory
    from app.services.operation_assessment import service as assessment
    def run(db):
        grades.reviewable(db, user, sid)
        evaluation = assessment.view(db, sid)
        grade = db.get(ExamGrade, sid)
        if not evaluation or evaluation['id'] != body.evaluation_id or evaluation['status'] != 'ready':
            ops.fail('请核对最新且证据完整的评价结果')
        if not grade or grade.revision != body.grade_revision or grade.score_cents is None:
            ops.fail('请先保存最新最终成绩')
        if grade.score_cents != evaluation['suggested_score'] * 100 and not body.reason.strip():
            ops.fail('人工调整建议分时请填写调整理由', 422)
        row = db.get(ExamAssessmentReview, sid)
        values = dict(evaluation_id=evaluation['id'], grade_revision=grade.revision, reason=body.reason.strip() or None,
                      reviewer_id=user.id, confirmed_at=service.now())
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            db.add(ExamAssessmentReview(session_id=sid, **values))
        db.add(ExamAssessmentReviewHistory(session_id=sid, content={
            'evaluation_id':evaluation['id'], 'grade_revision':grade.revision,
            'reason':values['reason'], 'reviewer_id':user.id,
            'confirmed_at':service.iso(values['confirmed_at']), 'score':grade.score_cents / 100}))
        return {'status': 'confirmed', 'grade_revision': grade.revision}
    return transaction(db, run)


@router.post('/attempts/{sid}/student-commentary')
def student_commentary(sid: str, body: GradeRevision, db: Session = Depends(get_db), user: User = Depends(manager)):
    from app.services.operation_assessment.commentary import generate
    return generate(db, user, sid, body.revision)


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


@router.get('/reviews')
def review_queue(page: int = Query(1, ge=1), exam_id: int | None = Query(None, ge=1),
                 status: Literal['all','pending','published'] = 'pending', search: str = Query('', max_length=150),
                 db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, exam_review_queue.listing, user, page, exam_id, status, search)


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
def begin(eid: int, body: Begin, db: Session = Depends(get_db), user: User = Depends(exam_student)):
    return transaction(db, service.begin, user, eid, body.fullscreen)


@router.get('/attempts/{sid}')
def detail(sid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return transaction(db, service.get_detail, user, sid)


@router.post('/attempts/{sid}/sync')
def sync(sid: str, body: Sync, db: Session = Depends(get_db), user: User = Depends(exam_student)):
    observation = service.readonly_sync(db, user, sid, body)
    if observation is not None:
        return observation
    return transaction(db, service.sync, user, sid, body)


@router.post('/attempts/{sid}/events')
def click(sid: str, body: Click, light: bool = False, db: Session = Depends(get_db), user: User = Depends(exam_student)):
    return transaction(db, service.click, user, sid, body, light=light)


@router.post('/attempts/{sid}/submit')
def submit(sid: str, body: Submit, db: Session = Depends(get_db), user: User = Depends(exam_student)):
    return transaction(db, service.submit, user, sid, body.expected_sequence)


@router.put('/attempts/{sid}/grade')
def save_grade(sid: str, body: GradeDraft, db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, grades.save, user, sid, body)


@router.post('/attempts/{sid}/grade/confirm')
def confirm_grade(sid: str, body: GradeRevision, db: Session = Depends(get_db), user: User = Depends(manager)):
    return transaction(db, grades.confirm, user, sid, body.revision)


@router.post('/attempts/{sid}/grade/publish')
def publish_grade(sid: str, body: GradeDraft, db: Session = Depends(get_db), user: User = Depends(manager)):
    # Revision-only requests retain the earlier API contract; the current page submits its inputs.
    if body.model_fields_set == {'revision'}:
        return transaction(db, grades.publish, user, sid, body.revision)
    return transaction(db, grades.publish_current, user, sid, body)


@router.get('/attempts/{sid}/log.json')
def download(sid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return json_download(transaction(db, service.download, user, sid), 'exam-log.json')
