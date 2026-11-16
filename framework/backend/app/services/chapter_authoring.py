"""Local question edits with immutable practice snapshots and durable removal markers."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, update
from app.models.chapter_bank import ChapterBankQuestion
from app.services import chapter_bank as bank, chapter_practice as practice


def find(db, qid):
    row = db.get(ChapterBankQuestion, qid)
    if row is None or not practice.valid_rule(row, practice.effective_rule(row, practice.load_rules())):
        raise HTTPException(404, '题目不存在或已删除')
    return row


def revision(row):
    return row.content.get('_management', {}).get('revision', 0)


def detail(row):
    q = row.content
    rule = practice.effective_rule(row, practice.load_rules()) or {}
    answer = deepcopy(q.get('answer'))
    if row.kind == 'multi' and isinstance(answer, str):
        answer = list(answer)
    if row.kind == 'cell' and isinstance(answer, str):
        answer = [answer]
    if row.kind == 'cell' and (not isinstance(answer, list) or not answer or any(not isinstance(v, str) for v in answer)):
        answer = ['']
    if row.kind == 'true_false' and type(answer) is not bool:
        answer = None
    return {**bank.present_question(q), 'id': row.id, 'chapter': row.chapter, 'kind': row.kind,
            'answer': answer, 'options': bank.readable_options(q.get('options')),
            'accepted': deepcopy(rule.get('accepted', [])), 'explanation': q.get('explanation') or q.get('notes') or '',
            'source_reference': q.get('source_reference', ''), 'revision': revision(row),
            'can_practice': practice.valid_rule(row, rule)}


def listing(db, **filters):
    data = bank.question_list(db, **filters)
    data['items'] = [detail(find(db, item['id'])) for item in data['items']]
    return data


def content(body, qid, previous=None):
    stem, source = body.stem.strip(), body.source_reference.strip()
    if not stem or not source:
        raise HTTPException(422, '请填写题干和命题依据')
    options = [value.strip() for value in body.options]
    answer = deepcopy(body.answer)
    accepted = []
    if body.kind in ('choice', 'multi'):
        if not 2 <= len(options) <= 12 or any(not value or len(value) > 3000 for value in options):
            raise HTTPException(422, '选择题需要2至12个非空选项，每项不超过3000字')
        keys = {chr(65+i) for i in range(len(options))}
        if body.kind == 'choice' and (not isinstance(answer, str) or answer not in keys):
            raise HTTPException(422, '请选择一个有效的标准答案')
        if body.kind == 'multi' and (not isinstance(answer, list) or not answer or
                len(set(answer)) != len(answer) or not set(answer) <= keys):
            raise HTTPException(422, '请选择有效且不重复的标准答案')
    elif body.kind == 'true_false':
        if type(answer) is not bool:
            raise HTTPException(422, '请明确选择判断题的正确或错误')
    else:
        if (not isinstance(answer, list) or not 1 <= len(answer) <= 20 or
                any(not value.strip() or len(value) > 1000 for value in answer)):
            raise HTTPException(422, '请逐空填写标准答案，每空不超过1000字')
        answer = [value.strip() for value in answer]
        if body.accepted and len(body.accepted) != len(answer):
            raise HTTPException(422, '可接受写法必须与填空数量一致')
        for index, value in enumerate(answer):
            variants = body.accepted[index] if body.accepted else []
            if len(variants) > 30 or any(not v.strip() or len(v) > 1000 for v in variants):
                raise HTTPException(422, '每空最多30种非空写法，每种不超过1000字')
            accepted.append(list(dict.fromkeys([value, *(v.strip() for v in variants)])))
    q = deepcopy(previous or {})
    q.update(id=qid, chapter=body.chapter, kind=body.kind, stem=stem,
             options=[{'key': chr(65+i), 'text': value} for i, value in enumerate(options)] if body.kind in ('choice','multi') else [],
             answer=answer, answer_status='teacher_verified', explanation=body.explanation.strip(),
             source_reference=source, answer_evidence=source)
    # A teacher edit replaces partial source answers and obsolete rule metadata.
    q.pop('partial_answer', None)
    q.pop('_practice_rule', None)
    rule = {'id': qid, 'kind': body.kind, 'signature': practice.signature(q)}
    if body.kind == 'cell':
        rule['accepted'] = accepted
    q['_practice_rule'] = rule
    return q


def stamp(q, user, number):
    q['_management'] = {'revision': number, 'editor_id': user.id,
                        'updated_at': datetime.now(timezone.utc).isoformat()}


def create(db, user, body):
    qid = 'custom-' + uuid4().hex
    q = content(body, qid)
    stamp(q, user, 1)
    row = ChapterBankQuestion(id=qid, chapter=body.chapter, kind=body.kind,
                              answer_status='teacher_verified', content=q)
    db.add(row); db.commit(); db.refresh(row)
    return detail(row)


def replace(db, user, row, q, expected):
    stamp(q, user, expected+1)
    result = db.execute(update(ChapterBankQuestion).where(
        ChapterBankQuestion.id == row.id,
        func.coalesce(ChapterBankQuestion.content['_management']['revision'].as_integer(), 0) == expected,
        bank.visible_question(),
    ).values(content=q, chapter=q['chapter'], kind=q['kind'], answer_status=q['answer_status']),
        execution_options={'synchronize_session': False})
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, '题目已被其他教师修改，请保留输入并刷新核对')
    db.commit(); db.refresh(row)
    return detail(row)


def edit(db, user, qid, body):
    row = find(db, qid)
    return replace(db, user, row, content(body, qid, row.content), body.revision)


def remove(db, user, qid, expected):
    row = find(db, qid)
    q = deepcopy(row.content)
    q['_deleted'] = True
    replace(db, user, row, q, expected)
    return {'deleted': True, 'id': qid}
