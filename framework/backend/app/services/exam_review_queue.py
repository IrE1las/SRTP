"""Submitted exam queue scoped to the teacher's own exams."""
from sqlalchemy import select
from app.models.exam import Exam, ExamAttempt, ExamParticipant
from app.services import exams


def listing(db, user, number, exam_id=None, status='pending', search=''):
    query = select(ExamAttempt).join(Exam, Exam.id == ExamAttempt.exam_id)
    if user.role == 'teacher':
        query = query.where(Exam.owner_id == user.id)
    if exam_id is not None:
        exams.managed(db, user, exam_id)
        query = query.where(ExamAttempt.exam_id == exam_id)
    rows = []
    counts = {'all': 0, 'pending': 0, 'published': 0}
    for attempt in db.scalars(query.order_by(ExamAttempt.started_at.desc(), ExamAttempt.session_id.desc())):
        exams.settle(db, attempt, exams.now())
        if attempt.submitted_at is None:
            continue
        item = exams.summary(db, attempt, user)
        item['identity'] = db.get(ExamParticipant, (attempt.exam_id, attempt.student_id)).identity_snapshot
        if search.strip().casefold() not in ' '.join(str(item['identity'].get(key) or '') for key in
                ('real_name', 'student_id', 'class_name')).casefold() + ' ' + (item['name'] or '').casefold():
            continue
        published = item['grade']['status'] == 'published'
        counts['all'] += 1
        counts['published' if published else 'pending'] += 1
        if status == 'pending' and published or status == 'published' and not published:
            continue
        rows.append(item)
    return {**exams.page(rows, number), 'counts': counts}
