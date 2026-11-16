"""Manual-only grading. Call mutations under exams.atomic and operations.LOCK."""
from sqlalchemy import select
from sqlalchemy.orm import object_session
from app.models.exam_grade import ExamGrade, ExamGradePublication, ExamGradeAudit
from app.services import exams, operations as ops


def published(db, sid):
    return db.scalar(select(ExamGradePublication).where(ExamGradePublication.session_id == sid)
                     .order_by(ExamGradePublication.version.desc()).limit(1))


def public_version(row):
    if row is None:
        return None
    # Student response allowlist: never include the mutable draft or audit.
    result = {'score': row.score_cents / 100, 'comment': row.comment, 'version': row.version,
              'published_at': exams.iso(row.published_at)}
    from app.models.operation_assessment import ExamPublishedAssessment
    db = object_session(row)
    snapshot = db.get(ExamPublishedAssessment, row.id) if db else None
    if snapshot:
        result['assessment'] = snapshot.content
    return result


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


def publish(db, user, sid, revision, *, assessment_snapshot=None):
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
    publication = ExamGradePublication(session_id=sid, version=previous.version + 1 if previous else 1,
        source_revision=revision, score_cents=grade.score_cents, comment=grade.comment,
        publisher_id=user.id, published_at=exams.now())
    db.add(publication)
    db.flush()
    if assessment_snapshot:
        from app.models.operation_assessment import ExamPublishedAssessment
        db.add(ExamPublishedAssessment(publication_id=publication.id, content=assessment_snapshot))
    grade.status = 'published'
    grade.revision += 1
    grade.updated_at = exams.now()
    audit(db, grade, user, 'publish')
    return manager_view(db, sid, evidence=True)


def publish_current(db, user, sid, body):
    """Save, confirm and publish the reviewed inputs in one atomic transaction."""
    reviewable(db, user, sid)
    if body.score is None:
        ops.fail('请填写最终成绩后再发布', 422)
    comment = (body.comment or '').strip() or None
    source_revision = body.revision + 2  # Save and confirmation each advance one revision.
    previous = db.scalar(select(ExamGradePublication).where(
        ExamGradePublication.session_id == sid, ExamGradePublication.source_revision == source_revision))
    if previous:
        if previous.score_cents != int(body.score * 100) or previous.comment != comment:
            ops.fail('成绩已被修改，请保留本地输入并刷新核对')
        return manager_view(db, sid, evidence=True)
    snapshot = None
    from app.models.operation_assessment import ExamAssessmentReview
    from app.services.operation_assessment import service as assessment
    reviewed = db.get(ExamAssessmentReview, sid)
    grade = db.get(ExamGrade, sid)
    evaluation = assessment.view(db, sid)
    if reviewed and grade and reviewed.grade_revision == body.revision and grade.revision == body.revision and (
        grade.score_cents == int(body.score * 100) and evaluation and reviewed.evaluation_id == evaluation['id'] and evaluation['status'] == 'ready'):
        snapshot = {'dimensions': evaluation['dimensions'], 'milestones': evaluation['milestones'],
                    'teacher_adjusted': grade.score_cents != evaluation['suggested_score'] * 100,
                    'deductions': [{'description': e['message'], 'points': e['points'], 'recovered': e['recovered']} for e in evaluation['episodes']],
                    'cap_reasons': evaluation['cap_reasons']}
    save(db, user, sid, body)
    confirm(db, user, sid, body.revision + 1)
    return publish(db, user, sid, source_revision, assessment_snapshot=snapshot)
