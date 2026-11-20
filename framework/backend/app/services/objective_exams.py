"""Frozen objective papers using exactly the reviewed practice grading rules."""
from copy import deepcopy
from uuid import uuid4
from fastapi import HTTPException
from app.models.exam import Exam, ExamAttempt, ExamParticipant, ObjectiveExamPaper, ObjectiveExamResponse
from app.services import chapter_practice as practice, exams, operations as ops


def paper(db, exam):
    return db.get(ObjectiveExamPaper, exam.id)


def configure(db, exam, kind, questions):
    existing = paper(db, exam)
    if kind == 'operation':
        if questions:
            ops.fail('操作考试不能配置客观题试卷', 422)
        if existing:
            db.delete(existing)
        return
    if exam.version_id is not None:
        ops.fail('客观题考试不能配置操作题版本', 422)
    ids = [item['question_id'] for item in questions]
    if len(ids) != len(set(ids)):
        ops.fail('试卷不能重复选题', 422)
    available = {row.id for row, _ in practice.available_questions(db)}
    if set(ids) - available:
        ops.fail('所选题目已删除、变更或暂不可自动判分，请重新选题', 422)
    if existing:
        existing.questions = deepcopy(questions)
    else:
        db.add(ObjectiveExamPaper(exam_id=exam.id, questions=deepcopy(questions)))
    db.flush()


def catalogue(db, page, search='', chapter=None, kind=None):
    rows = [practice.public_question(row.content, rule) for row, rule in practice.available_questions(db, chapter)
            if (not kind or row.kind == kind)]
    term = search.strip().casefold()
    rows = [row for row in rows if term in (row['stem'] + ' ' + row['id']).casefold()]
    rows.sort(key=lambda row: (row['chapter'], row['id']))
    return exams.page(rows, page)


def freeze(db, selected):
    if not selected.questions or sum(item['points'] for item in selected.questions) != 100:
        ops.fail('客观题试卷须至少选择一道题，且总分为100分', 422)
    pool = {row.id: (row, rule) for row, rule in practice.available_questions(db)}
    if any(item['question_id'] not in pool for item in selected.questions):
        ops.fail('所选题目已删除、变更或暂不可自动判分，请重新选题', 422)
    items = []
    for item in selected.questions:
        row, rule = pool[item['question_id']]
        items.append({**item, 'question': deepcopy(row.content), 'rule': deepcopy(rule),
                      'public': practice.public_question(row.content, rule)})
    return {'kind': 'objective', 'title': '客观题试卷', 'total_points': 100, 'items': items}


def public_paper(frozen):
    return {'kind': 'objective', 'title': frozen['title'], 'total_points': frozen['total_points'],
            'items': [{**deepcopy(item['public']), 'points': item['points']} for item in frozen['items']]}


def begin(db, user, exam, at):
    from datetime import timedelta
    sid = str(uuid4())
    attempt = ExamAttempt(session_id=sid, exam_id=exam.id, student_id=user.id, started_at=at,
                          deadline=min(at + timedelta(minutes=exam.duration_minutes), exam.closes_at))
    db.add(attempt)
    db.flush()
    db.add(ObjectiveExamResponse(session_id=sid, answers={}))
    db.flush()
    return detail(db, user, attempt)


def response(db, attempt):
    row = db.get(ObjectiveExamResponse, attempt.session_id)
    if row is None:
        ops.fail('该答卷不是客观题考试', 422)
    return row


def detail(db, user, attempt):
    from app.services import exam_grades as grades
    from app.models.exam import ExamControlEvent
    from sqlalchemy import select
    exam = db.get(Exam, attempt.exam_id)
    row = response(db, attempt)
    result = {**exams.summary(db, attempt, user), 'kind': 'objective',
              'question': public_paper(exam.question_snapshot), 'answers': deepcopy(row.answers),
              'answer_revision': row.revision, 'opens_at': exams.iso(exam.opens_at),
              'closes_at': exams.iso(exam.closes_at), 'duration_minutes': exam.duration_minutes,
              'identity': db.get(ExamParticipant, (exam.id, attempt.student_id)).identity_snapshot,
              'console': None}
    if user.role != 'student':
        result['objective_evaluation'] = deepcopy(row.evaluation)
        result['grade'] = grades.manager_view(db, attempt.session_id, evidence=True)
        result['control_events'] = [event.content for event in db.scalars(select(ExamControlEvent).where(
            ExamControlEvent.session_id == attempt.session_id).order_by(ExamControlEvent.id))]
    elif attempt.submitted_at and exams.now() >= exam.closes_at and grades.published(db, attempt.session_id):
        # Do not disclose answer keys to early finishers while classmates can still sit.
        result['objective_evaluation'] = deepcopy(row.evaluation)
    return result


def validate_answers(frozen, answers):
    questions = {item['question_id']: item for item in frozen['items']}
    if set(answers) - questions.keys():
        ops.fail('答案包含本试卷以外的题目', 422)
    for qid, answer in answers.items():
        item = questions[qid]
        question = item['public']
        keys = {option['key'] for option in question['options']}
        kind = question['kind']
        if answer is None:
            continue
        valid = False
        if kind == 'true_false':
            valid = type(answer) is bool
        elif kind == 'choice':
            valid = isinstance(answer, str) and answer in keys
        elif kind == 'multi':
            valid = (isinstance(answer, list) and all(isinstance(value, str) for value in answer)
                     and len(set(answer)) == len(answer) and set(answer) <= keys)
        elif kind == 'cell':
            valid = (isinstance(answer, list) and len(answer) == question['blank_count']
                     and all(isinstance(value, str) and len(value) <= 2000 for value in answer))
        if not valid:
            ops.fail('答案格式不正确，请检查选项和填空数量', 422)


def save(db, user, sid, body):
    attempt = exams.owned(db, user, sid)
    row = response(db, attempt)
    exams.settle(db, attempt, exams.now())
    if attempt.submitted_at is not None:
        # Keep the server-clock settlement even when this late write is rejected.
        db.commit()
        ops.fail('考试已结束，不能修改答案')
    if attempt.fullscreen_state != 'inside':
        ops.fail('请先恢复全屏再保存答案')
    if body.revision != row.revision:
        if body.revision == row.revision - 1 and body.answers == row.answers:
            return detail(db, user, attempt)
        ops.fail('答案已在其他页面修改，请保留本地答案并刷新核对')
    validate_answers(db.get(Exam, attempt.exam_id).question_snapshot, body.answers)
    row.answers = deepcopy(body.answers)
    row.revision += 1
    attempt.revision += 1
    db.flush()
    return detail(db, user, attempt)


def seal(db, attempt):
    row = response(db, attempt)
    frozen = db.get(Exam, attempt.exam_id).question_snapshot
    results = []
    for item in frozen['items']:
        answer = row.answers.get(item['question_id'])
        try:
            feedback = practice.grade(item, answer)
        except HTTPException as exc:
            if exc.status_code != 422:
                raise
            q = item['question']
            feedback = {'correct': False, 'submitted_answer': answer, 'correct_answer': q['answer'],
                        'blank_results': [], 'explanation': q.get('explanation') or q.get('notes') or '',
                        'answer_evidence': q.get('answer_evidence') or ''}
            if q['kind'] == 'cell':
                blanks = answer if isinstance(answer, list) else [''] * len(item['rule']['accepted'])
                feedback['blank_results'] = practice.blank_matches(blanks, item['rule']['accepted'], item['rule'].get('unordered') is True)
        results.append({'question_id': item['question_id'], 'points': item['points'],
                        'earned': item['points'] if feedback['correct'] else 0, **feedback})
    row.evaluation = {'score': sum(item['earned'] for item in results), 'total_points': 100, 'items': results}
    db.flush()
