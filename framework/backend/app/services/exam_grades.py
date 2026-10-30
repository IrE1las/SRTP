"""Manual-only grading. Call mutations under exams.atomic and operations.LOCK."""
from sqlalchemy import select
from app.models.exam_grade import ExamGrade, ExamGradePublication, ExamGradeAudit
from app.services import exams, operations as ops


def published(db, sid):
    return db.scalar(select(ExamGradePublication).where(ExamGradePublication.session_id == sid)
                     .order_by(ExamGradePublication.version.desc()).limit(1))


def public_version(row):
    if row is None:
        return None
    # Student response allowlist: never include the mutable draft or audit.
    return {'score': row.score_cents / 100, 'comment': row.comment, 'version': row.version,
            'published_at': exams.iso(row.published_at)}


def manager_view(db, sid, *, evidence=False):
    grade = db.get(ExamGrade, sid)
    result = {'revision': grade.revision if grade else 0, 'status': grade.status if grade else 'ungraded',
              'score': grade.score_cents / 100 if grade and grade.score_cents is not None else None,
              'comment': grade.comment if grade else None,
              'editor_id': grade.editor_id if grade else None,
              'updated_at': exams.iso(grade.updated_at) if grade else None,
              'confirmed_by': grade.confirmed_by if grade else None,
              'confirmed_at': exams.iso(grade.confirmed_at) if grade else None,
              'published': public_version(published(db, sid))}
    if evidence:
        result['publications'] = [{**public_version(row), 'publisher_id': row.publisher_id,
                                   'source_revision': row.source_revision}
            for row in db.scalars(select(ExamGradePublication).where(ExamGradePublication.session_id == sid)
                                  .order_by(ExamGradePublication.version.desc()))]
        result['audit'] = [{'revision': row.revision, 'action': row.action, 'actor_id': row.actor_id,
                           'occurred_at': exams.iso(row.occurred_at), 'snapshot': row.snapshot}
            for row in db.scalars(select(ExamGradeAudit).where(ExamGradeAudit.session_id == sid)
                                  .order_by(ExamGradeAudit.revision.desc()))]
    return result


def reviewable(db, user, sid):
    # A student may own the attempt but must never reach manual grading operations.
    if user.role not in {'teacher', 'admin'}:
        ops.fail('无权批阅考试', 403)
    attempt = exams.owned(db, user, sid)
    exams.settle(db, attempt, exams.now())
    if attempt.submitted_at is None:
        ops.fail('答卷尚未交卷，不能录入成绩')
    return attempt


def audit(db, grade, user, action):
    db.add(ExamGradeAudit(session_id=grade.session_id, revision=grade.revision, action=action,
                         actor_id=user.id, occurred_at=exams.now(), snapshot={
                             'score': grade.score_cents / 100 if grade.score_cents is not None else None,
                             'comment': grade.comment, 'status': grade.status,
                             'confirmed_by': grade.confirmed_by, 'confirmed_at': exams.iso(grade.confirmed_at)}))
    db.flush()


def save(db, user, sid, body):
    reviewable(db, user, sid)
    grade = db.get(ExamGrade, sid)
    if body.revision != (grade.revision if grade else 0):
        ops.fail('成绩已被修改，请保留本地输入并刷新核对')
    if grade is None:
        grade = ExamGrade(session_id=sid, revision=0)
        db.add(grade)
    grade.revision += 1
    grade.status = 'draft'
    grade.score_cents = int(body.score * 100) if body.score is not None else None
    grade.comment = (body.comment or '').strip() or None
    grade.editor_id = user.id
    grade.updated_at = exams.now()
    grade.confirmed_by = grade.confirmed_at = None
    audit(db, grade, user, 'save')
    return manager_view(db, sid, evidence=True)


def confirm(db, user, sid, revision):
    reviewable(db, user, sid)
    grade = db.get(ExamGrade, sid)
    if grade and grade.status == 'confirmed' and grade.revision == revision + 1:
        return manager_view(db, sid, evidence=True)
    if not grade or grade.revision != revision or grade.status != 'draft':
        ops.fail('请先保存最新成绩草稿，再确认')
    if grade.score_cents is None:
        ops.fail('请先填写最终成绩并保存草稿', 422)
    grade.status = 'confirmed'
    grade.revision += 1
    grade.confirmed_by = user.id
    grade.confirmed_at = grade.updated_at = exams.now()
    audit(db, grade, user, 'confirm')
    return manager_view(db, sid, evidence=True)


def publish(db, user, sid, revision):
    reviewable(db, user, sid)
    # Repeating a successful publish never creates another version, even after a correction.
    old = db.scalar(select(ExamGradePublication).where(ExamGradePublication.session_id == sid,
                                                     ExamGradePublication.source_revision == revision))
    if old:
        return manager_view(db, sid, evidence=True)
    grade = db.get(ExamGrade, sid)
    if not grade or grade.revision != revision or grade.status != 'confirmed' or grade.score_cents is None:
        ops.fail('请先确认最新成绩；确认后仍需单独发布')
    previous = published(db, sid)
    db.add(ExamGradePublication(session_id=sid, version=previous.version + 1 if previous else 1,
        source_revision=revision, score_cents=grade.score_cents, comment=grade.comment,
        publisher_id=user.id, published_at=exams.now()))
    grade.status = 'published'
    grade.revision += 1
    grade.updated_at = exams.now()
    audit(db, grade, user, 'publish')
    return manager_view(db, sid, evidence=True)
