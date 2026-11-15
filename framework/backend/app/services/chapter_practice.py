"""Answer-validated practice, isolated from laboratory scoring."""
import copy
import hashlib
import json
import secrets
import unicodedata
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models.chapter_bank import ChapterBankQuestion
from app.models.chapter_practice import PracticeAttempt, PracticeBookmark, utc_now
from app.services.chapter_bank import CHAPTERS, PENDING, STATUSES, readable_options
from app.services.chapter_bank_presentation import present_question

RULES_PATH = Path(__file__).resolve().parents[4] / 'ai_design/station/chapter_practice_rules.json'
RANDOM = secrets.SystemRandom()


def normalize(value):
    return ''.join(unicodedata.normalize('NFKC', value).split()).casefold()


def signature(question):
    payload = {key: question.get(key) for key in
               ('id', 'chapter', 'kind', 'stem', 'options', 'answer', 'answer_status')}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def load_rules():
    """Missing or invalid review files disable drawing rather than guessing answers."""
    try:
        data = json.loads(RULES_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('questions'), list):
        return {}
    rules = {}
    for rule in data['questions']:
        if isinstance(rule, dict) and isinstance(rule.get('id'), str):
            # A duplicate review is ambiguous and therefore cannot authorize a question.
            qid = rule['id']
            rules[qid] = rule if qid not in rules else None
    return rules


def valid_rule(row, rule):
    q = row.content
    if (not isinstance(q, dict) or not rule or rule.get('kind') != row.kind
            or q.get('id') != row.id or q.get('chapter') != row.chapter or q.get('kind') != row.kind
            or q.get('answer_status') not in STATUSES or q.get('answer_status') in PENDING
            or q.get('images') or q.get('media_review_required') or rule.get('signature') != signature(q)):
        return False
    answer, kind = q.get('answer'), row.kind
    keys = {option['key'] for option in readable_options(q.get('options'))}
    if kind == 'choice':
        return isinstance(answer, str) and answer in keys
    if kind == 'multi':
        # Reviewed source keys sometimes use the compact form "AC".
        return (isinstance(answer, (list, str)) and bool(answer) and all(isinstance(a, str) for a in answer)
                and len(set(answer)) == len(answer) and set(answer) <= keys)
    if kind == 'true_false':
        return type(answer) is bool
    if kind == 'cell':
        accepted = rule.get('accepted')
        return (isinstance(accepted, list) and bool(accepted)
                and all(isinstance(group, list) and bool(group)
                        and all(isinstance(v, str) and bool(normalize(v)) for v in group) for group in accepted)
                and (isinstance(answer, str) and bool(answer.strip())
                     or isinstance(answer, list) and len(answer) == len(accepted)
                     and all(isinstance(v, str) and bool(v.strip()) for v in answer)))
    return False


def available_questions(db, chapter=None):
    rules = load_rules()
    query = db.query(ChapterBankQuestion)
    if chapter is not None:
        query = query.filter_by(chapter=chapter)
    return [(row, rules[row.id]) for row in query.all() if valid_rule(row, rules.get(row.id))]


def bookmark_ids(db, user_id, chapter=None):
    query = db.query(PracticeBookmark.question_id).filter(PracticeBookmark.user_id == user_id)
    if chapter is not None:
        query = query.join(ChapterBankQuestion, ChapterBankQuestion.id == PracticeBookmark.question_id).filter(
            ChapterBankQuestion.chapter == chapter)
    return [qid for (qid,) in query.order_by(PracticeBookmark.question_id).all()]


def chapters(db, user_id):
    available = available_questions(db)
    marked = set(bookmark_ids(db, user_id))
    all_rows = db.query(ChapterBankQuestion).filter(ChapterBankQuestion.kind != 'essay').all()
    return [dict(id=i, title=title,
                 available=sum(row.chapter == i for row, _ in available),
                 total_objective=sum(row.chapter == i for row in all_rows),
                 bookmarked=sum(row.chapter == i and row.id in marked for row, _ in available))
            for i, title in enumerate(CHAPTERS, 1)]


def public_attempt(db, attempt, user_id):
    q, rule = attempt.private_snapshot['question'], attempt.private_snapshot['rule']
    fields = ('id', 'chapter', 'kind', 'stem', 'scope', 'source_reference', 'source_url')
    question = {key: q.get(key, '') for key in fields}
    question.update(present_question(q))
    question['options'] = readable_options(q.get('options'))
    question['blank_count'] = len(rule['accepted']) if q['kind'] == 'cell' else 0
    return dict(id=attempt.id, question=question, submitted=attempt.submitted_at is not None,
                marked=db.get(PracticeBookmark, (user_id, attempt.question_id)) is not None,
                feedback=attempt.feedback if attempt.submitted_at is not None else None)


def draw(db, user_id, chapter, exclude_ids, bookmarked_only):
    pool = available_questions(db, chapter)
    if bookmarked_only:
        marked = set(bookmark_ids(db, user_id, chapter))
        pool = [(row, rule) for row, rule in pool if row.id in marked]
    if not pool:
        message = '本章暂无已收藏且可自动判分的题目' if bookmarked_only else '本章暂无经过答案核验、可自动判分的题目'
        raise HTTPException(404, message)
    excluded = set(exclude_ids)
    choices = [(row, rule) for row, rule in pool if row.id not in excluded]
    if not choices:
        last = exclude_ids[-1] if exclude_ids else None
        choices = [(row, rule) for row, rule in pool if row.id != last] or pool
    row, rule = RANDOM.choice(choices)
    attempt = PracticeAttempt(user_id=user_id, question_id=row.id, chapter=chapter,
                              private_snapshot=copy.deepcopy(dict(question=row.content, rule=rule)))
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return public_attempt(db, attempt, user_id)


def get_attempt(db, user_id, attempt_id):
    attempt = db.query(PracticeAttempt).filter_by(id=attempt_id, user_id=user_id).first()
    if attempt is None:
        raise HTTPException(404, '练习记录不存在')
    return attempt


def blank_matches(answer, accepted, unordered=False):
    normalized = [set(normalize(v) for v in group) for group in accepted]
    if not unordered:
        return [normalize(value) in group for value, group in zip(answer, normalized)]
    # Augmenting paths prevent a repeated answer from satisfying multiple blanks.
    assigned = {}

    def match(index, seen):
        for group_index, group in enumerate(normalized):
            if group_index in seen or normalize(answer[index]) not in group:
                continue
            seen.add(group_index)
            if group_index not in assigned or match(assigned[group_index], seen):
                assigned[group_index] = index
                return True
        return False

    for index in range(len(answer)):
        match(index, set())
    matched = set(assigned.values())
    return [index in matched for index in range(len(answer))]


def grade(snapshot, answer):
    q, rule = snapshot['question'], snapshot['rule']
    kind = q['kind']
    keys = {option['key'] for option in readable_options(q.get('options'))}
    blanks = []
    valid = False
    if kind == 'true_false':
        valid = type(answer) is bool
        correct = answer is q['answer']
    elif kind == 'choice':
        valid = isinstance(answer, str) and answer in keys
        correct = answer == q['answer']
    elif kind == 'multi':
        valid = (isinstance(answer, list) and bool(answer) and all(isinstance(a, str) for a in answer)
                 and len(set(answer)) == len(answer) and set(answer) <= keys)
        correct = valid and set(answer) == set(q['answer'])
    elif kind == 'cell':
        valid = (isinstance(answer, list) and len(answer) == len(rule['accepted'])
                 and all(isinstance(value, str) and bool(normalize(value)) for value in answer))
        if valid:
            blanks = blank_matches(answer, rule['accepted'], rule.get('unordered') is True)
        correct = valid and all(blanks)
    if not valid:
        raise HTTPException(422, '答案格式不正确：请选择有效选项、明确判断对错，或按空数填写所有答案')
    return dict(correct=bool(correct), submitted_answer=answer, correct_answer=q['answer'],
                blank_results=blanks, explanation=q.get('explanation') or q.get('notes') or '',
                answer_evidence=q.get('answer_evidence') or '')


def submit(db, user_id, attempt_id, answer):
    attempt = get_attempt(db, user_id, attempt_id)
    if attempt.submitted_at is None:
        feedback = grade(attempt.private_snapshot, answer)
        # The conditional write also makes concurrent first submissions immutable.
        db.execute(update(PracticeAttempt).where(PracticeAttempt.id == attempt_id,
                   PracticeAttempt.user_id == user_id, PracticeAttempt.submitted_at.is_(None)).values(
                       answer=answer, feedback=feedback, submitted_at=utc_now()),
                   execution_options={'synchronize_session': False})
        db.commit()
        db.refresh(attempt)
    return public_attempt(db, attempt, user_id)


def set_bookmark(db, user_id, qid, marked):
    if db.get(ChapterBankQuestion, qid) is None:
        raise HTTPException(404, '题目不存在')
    existing = db.get(PracticeBookmark, (user_id, qid))
    if marked and existing is None:
        db.add(PracticeBookmark(user_id=user_id, question_id=qid))
    elif not marked and existing is not None:
        db.delete(existing)
    try:
        db.commit()
    except IntegrityError:
        # Parallel marking of the same question is an idempotent operation.
        db.rollback()
        if not marked or db.get(PracticeBookmark, (user_id, qid)) is None:
            raise
    return dict(question_id=qid, marked=marked)
