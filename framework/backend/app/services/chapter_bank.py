"""Validated, insert-only collection import and answer-free chapter browsing."""
import copy
import json
import re
from pathlib import Path
from sqlalchemy import func, or_, case
from app.models.chapter_bank import ChapterBankQuestion
from app.models.chapter_practice import PracticeAttempt
from app.services.chapter_bank_presentation import present_question

BANK_PATH = Path(__file__).resolve().parents[4] / 'ai_design/station/chapter_question_bank.json'
CHAPTERS = ['进路选择与设备操作', '进路取消与人工解锁', '模拟行车与正常解锁',
            '故障现象与安全处理', '列车进路联锁表', '调车进路联锁表']
PENDING = ('pending', 'partial', 'platform_answer')
KINDS = ('choice', 'multi', 'true_false', 'cell', 'essay')
STATUSES = (*PENDING, 'source_explicit', 'material_supported', 'exam_answer_key', 'local_rule_checked')


def load_bank():
    return json.loads(BANK_PATH.read_text(encoding='utf-8'))


def import_bank(db, bank):
    """Validate the whole input first; do not overwrite local edits on repeat imports."""
    questions = bank.get('questions')
    if not isinstance(questions, list) or not questions:
        raise ValueError('题库内容为空')
    ids = set()
    for q in questions:
        if (not isinstance(q, dict) or not isinstance(q.get('id'), str)
                or not q['id'] or len(q['id']) > 50 or q['id'] in ids
                or type(q.get('chapter')) is not int or not 1 <= q['chapter'] <= 6
                or q.get('kind') not in KINDS or q.get('answer_status') not in STATUSES
                or not isinstance(q.get('stem'), str) or not q['stem'].strip()
                or not q.get('source_reference')):
            raise ValueError('题号、章节、题型或来源不完整')
        ids.add(q['id'])
    existing = {r[0] for r in db.query(ChapterBankQuestion.id).all()}
    created = 0
    for q in questions:
        if q['id'] in existing:
            continue
        db.add(ChapterBankQuestion(id=q['id'], chapter=q['chapter'], kind=q['kind'],
                                  answer_status=q['answer_status'], content=copy.deepcopy(q)))
        created += 1
    db.flush()
    return {'created': created, 'skipped': len(questions) - created}


def chapters(db):
    counts = db.query(ChapterBankQuestion.chapter, ChapterBankQuestion.kind,
                      ChapterBankQuestion.answer_status, func.count()).group_by(
                          ChapterBankQuestion.chapter, ChapterBankQuestion.kind,
                          ChapterBankQuestion.answer_status).all()
    result = []
    for number, title in enumerate(CHAPTERS, 1):
        rows = [(kind, status, n) for ch, kind, status, n in counts if ch == number]
        total = sum(n for _, _, n in rows)
        essay = sum(n for kind, _, n in rows if kind == 'essay')
        pending = sum(n for _, status, n in rows if status in PENDING)
        objective_pending = sum(n for kind, status, n in rows if kind != 'essay' and status in PENDING)
        result.append(dict(id=number, title=title, total=total, objective=total-essay,
                           essay=essay, pending=pending, ready=total-pending,
                           objective_pending=objective_pending, objective_ready=total-essay-objective_pending,
                           kinds={kind: sum(n for k, _, n in rows if k == kind) for kind in KINDS}))
    return result


def readable_options(raw):
    """Return labels and option text only, excluding embedded grading metadata."""
    if not isinstance(raw, list):
        return []
    result = []
    for i, option in enumerate(raw):
        key = chr(65+i)
        if isinstance(option, dict):
            text = option.get('text', '')
            key = str(option.get('key', key))
        elif isinstance(option, str):
            match = re.match(r'^\s*([A-Z])[.、．:)）]\s*(.*)$', option, re.S)
            key, text = match.groups() if match else (key, option)
        else:
            continue
        if isinstance(text, str) and text.strip():
            result.append(dict(key=key, text=text))
    return result


def question_list(db, chapter=None, *, page=1, limit=30, search='', kind='objective', status='all', user_id=None, progress='all'):
    query = db.query(ChapterBankQuestion)
    if chapter is not None:
        query = query.filter_by(chapter=chapter)
    history = None
    if user_id is not None:
        history = db.query(PracticeAttempt.question_id.label('qid'), func.count(PracticeAttempt.id).label('attempts'),
            func.max(case((PracticeAttempt.feedback['correct'].as_boolean().is_(True), 1), else_=0)).label('correct')
        ).filter(PracticeAttempt.user_id == user_id, PracticeAttempt.submitted_at.is_not(None)).group_by(PracticeAttempt.question_id).subquery()
        query = query.outerjoin(history, history.c.qid == ChapterBankQuestion.id)
        if progress == 'correct':
            query = query.filter(history.c.correct == 1)
        elif progress == 'not_correct':
            query = query.filter(func.coalesce(history.c.correct, 0) == 0)
        elif progress == 'unanswered':
            query = query.filter(history.c.qid.is_(None))
    if kind == 'objective':
        query = query.filter(ChapterBankQuestion.kind != 'essay')
    elif kind != 'all':
        query = query.filter(ChapterBankQuestion.kind == kind)
    if status == 'pending':
        query = query.filter(ChapterBankQuestion.answer_status.in_(PENDING))
    elif status == 'answered':
        query = query.filter(~ChapterBankQuestion.answer_status.in_(PENDING))
    if search.strip():
        query = query.filter(or_(
            ChapterBankQuestion.content['stem'].as_string().contains(search.strip(), autoescape=True),
            ChapterBankQuestion.content['source_reference'].as_string().contains(search.strip(), autoescape=True)))
    total = query.count()
    records = query.order_by(ChapterBankQuestion.chapter, ChapterBankQuestion.id).offset((page-1)*limit).limit(limit).all()
    progress_by_id = {}
    rules = {}
    if user_id is not None:
        progress_by_id = {qid: (attempts, bool(correct)) for qid, attempts, correct in db.query(history).filter(history.c.qid.in_([r.id for r in records]))}
        from app.services.chapter_practice import load_rules, valid_rule
        rules = load_rules()
    fields = ('id', 'chapter', 'stem', 'kind', 'answer_status', 'scope', 'source_reference', 'source_url', 'source_kind', 'batch')
    items = []
    for row in records:
        item = {k: row.content.get(k, '') for k in fields}
        item.update(present_question(row.content))
        item.update(has_image=bool(item['images']), notes='', options=readable_options(row.content.get('options')))
        if user_id is not None:
            attempted, ever_correct = progress_by_id.get(row.id, (0, False))
            item.update(attempted=bool(attempted), ever_correct=ever_correct, can_practice=bool(valid_rule(row, rules.get(row.id))))
        items.append(item)
    return dict(total=total, page=page, limit=limit, items=items)
