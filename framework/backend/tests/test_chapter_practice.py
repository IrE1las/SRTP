"""Practice contract; the local app deliberately runs no production startup hooks."""
from types import SimpleNamespace
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chapter_bank import router
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.chapter_bank import ChapterBankQuestion
from app.services import chapter_practice as service


@pytest.fixture()
def practice_client(db_session):
    app = FastAPI()
    app.include_router(router, prefix='/api/chapter-bank')
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        yield client, app


def test_practice_requires_authenticated_reader(practice_client):
    client, app = practice_client
    assert client.get('/api/chapter-bank/practice/chapters').status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='student')
    response = client.get('/api/chapter-bank/practice/chapters')
    assert response.status_code == 200
    assert len(response.json()) == 6
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='guest')
    assert client.get('/api/chapter-bank/practice/chapters').status_code == 403


@pytest.fixture()
def practice_bank(practice_client, db_session, tmp_path, monkeypatch):
    client, app = practice_client
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='student')
    questions = [
        dict(id='choice', chapter=1, kind='choice', answer='B', options=['A. 第一', 'B. 第二']),
        dict(id='multi', chapter=1, kind='multi', answer=['A', 'C'], options=['A. 甲', 'B. 乙', 'C. 丙']),
        dict(id='bool', chapter=2, kind='true_false', answer=False),
        dict(id='cell', chapter=3, kind='cell', answer=['2', '闭塞']),
        dict(id='pending', chapter=1, kind='choice', answer='A', answer_status='pending'),
        dict(id='stale', chapter=1, kind='choice', answer='A'),
        dict(id='unruled', chapter=1, kind='choice', answer='A'),
        dict(id='image', chapter=1, kind='choice', answer='A', images=['diagram.png']),
    ]
    rules = []
    for q in questions:
        q.update(stem=f"题目{q['id']}", source_reference='教学资料', source_url='https://example.org',
                 scope='本章', explanation='资料明确说明此答案', answer_evidence='第3页')
        q.setdefault('answer_status', 'source_explicit')
        q.setdefault('options', [])
        signature = hashlib.sha256(json.dumps({k: q.get(k) for k in
            ('id', 'chapter', 'kind', 'stem', 'options', 'answer', 'answer_status')},
            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if q['id'] != 'unruled':
            rules.append(dict(id=q['id'], signature=signature, kind=q['kind'],
                              accepted=[['2', '二', '两'], ['闭塞']]))
        if q['id'] == 'stale':
            q['stem'] += '本地修改'
        db_session.add(ChapterBankQuestion(id=q['id'], chapter=q['chapter'], kind=q['kind'],
                                          answer_status=q['answer_status'], content=q))
    db_session.commit()
    path = tmp_path / 'rules.json'
    path.write_text(json.dumps(dict(version=1, questions=rules)), encoding='utf-8')
    monkeypatch.setattr(service, 'RULES_PATH', path)
    return client, app


def draw(client, chapter=1, **body):
    return client.post(f'/api/chapter-bank/practice/chapters/{chapter}/draw', json=body)


def draw_question(client, qid):
    chapter = {'bool': 2, 'cell': 3}.get(qid, 1)
    return draw(client, chapter, exclude_ids=[other for other in ('choice', 'multi') if other != qid]).json()


def test_only_signed_ready_imageless_questions_are_available(practice_bank):
    client, app = practice_bank
    rows = client.get('/api/chapter-bank/practice/chapters').json()
    assert rows[0]['available'] == 2
    assert rows[0]['total_objective'] == 6
    assert rows[1]['available'] == 1
    assert rows[3]['available'] == 0
    assert draw(client, 4).status_code == 404
    assert draw(client, 7).status_code == 422


def test_draw_hides_answers_and_uses_immutable_snapshot(practice_bank, db_session):
    client, app = practice_bank
    attempt = draw_question(client, 'choice')
    assert attempt['question']['id'] == 'choice'
    assert attempt['question']['options'] == [{'key': 'A', 'text': '第一'}, {'key': 'B', 'text': '第二'}]
    assert attempt['question']['blank_count'] == 0
    assert attempt['submitted'] is False and attempt['feedback'] is None
    for secret in ('answer', 'accepted', 'explanation', 'answer_evidence', 'answer_status'):
        assert secret not in attempt['question']
    row = db_session.get(ChapterBankQuestion, 'choice')
    row.content = {**row.content, 'stem': '已更改', 'answer': 'A'}
    db_session.commit()
    submitted = client.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit", json={'answer': 'B'})
    assert submitted.status_code == 200
    assert submitted.json()['question']['stem'] == '题目choice'
    assert submitted.json()['feedback']['correct'] is True
    assert submitted.json()['feedback']['correct_answer'] == 'B'
    assert submitted.json()['feedback']['answer_evidence'] == '第3页'
    repeated = client.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit", json={'answer': 'A'})
    assert repeated.json() == submitted.json()
    assert client.get(f"/api/chapter-bank/practice/attempts/{attempt['id']}").json() == submitted.json()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role='teacher')
    assert client.get(f"/api/chapter-bank/practice/attempts/{attempt['id']}").status_code == 404
    assert client.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit", json={'answer': 'B'}).status_code == 404


@pytest.mark.parametrize('qid, answer, correct, blanks', [
    ('choice', 'B', True, []), ('choice', 'A', False, []),
    ('multi', ['C', 'A'], True, []), ('multi', ['C'], False, []),
    ('bool', False, True, []), ('bool', True, False, []),
    ('cell', [' 二 ', '闭　塞'], True, [True, True]),
    ('cell', ['两', '闭塞'], True, [True, True]),
    ('cell', ['22', '闭塞'], False, [False, True]),
])
def test_grading_uses_each_kind_and_explicit_blank_aliases(practice_bank, qid, answer, correct, blanks):
    client, _ = practice_bank
    attempt = draw_question(client, qid)
    response = client.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit", json={'answer': answer})
    assert response.status_code == 200, response.text
    feedback = response.json()['feedback']
    assert feedback['correct'] is correct
    assert feedback['blank_results'] == blanks
    assert feedback['submitted_answer'] == answer
    assert feedback['explanation'] == '资料明确说明此答案'


@pytest.mark.parametrize('qid, answer', [
    ('choice', ''), ('choice', 'Z'), ('choice', ['B']), ('choice', False),
    ('multi', []), ('multi', ['A', 'A']), ('multi', ['Z']), ('multi', 'A'),
    ('bool', ''), ('bool', 'false'), ('bool', 0), ('bool', []),
    ('cell', ['2']), ('cell', ['2', '']), ('cell', ['2', '闭塞', '多余']),
    ('cell', '2'), ('cell', [2, '闭塞']),
])
def test_invalid_answers_do_not_consume_attempt(practice_bank, qid, answer):
    client, _ = practice_bank
    attempt = draw_question(client, qid)
    url = f"/api/chapter-bank/practice/attempts/{attempt['id']}"
    response = client.post(url + '/submit', json={'answer': answer})
    assert response.status_code == 422, response.text
    assert client.get(url).json()['submitted'] is False


def test_bookmarks_are_persistent_scoped_and_filter_draw(practice_bank, db_session):
    client, app = practice_bank
    prefix = '/api/chapter-bank/practice'
    assert draw(client, bookmarked_only=True).status_code == 404
    assert client.put(prefix + '/bookmarks/choice', json={'marked': True}).json() == {'question_id': 'choice', 'marked': True}
    client.put(prefix + '/bookmarks/choice', json={'marked': True})
    db_session.expire_all()
    assert client.get(prefix + '/bookmarks?chapter=1').json() == {'items': ['choice']}
    assert client.get(prefix + '/bookmarks?chapter=2').json() == {'items': []}
    assert draw(client, bookmarked_only=True).json()['question']['id'] == 'choice'
    assert draw(client, bookmarked_only=True).json()['marked'] is True
    assert client.get(prefix + '/chapters').json()[0]['bookmarked'] == 1
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role='admin')
    assert client.get(prefix + '/bookmarks').json() == {'items': []}
    assert draw(client, bookmarked_only=True).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='student')
    assert client.put(prefix + '/bookmarks/choice', json={'marked': False}).json()['marked'] is False
    assert client.get(prefix + '/bookmarks').json() == {'items': []}
    assert client.put(prefix + '/bookmarks/missing', json={'marked': True}).status_code == 404


def test_draw_exclusions_reset_without_immediate_repeat_or_crossing_chapter(practice_bank):
    client, _ = practice_bank
    assert draw(client, exclude_ids=['choice']).json()['question']['id'] == 'multi'
    assert draw(client, exclude_ids=['choice', 'multi']).json()['question']['id'] == 'choice'
    assert draw(client, 2, exclude_ids=['bool']).json()['question']['id'] == 'bool'
    for _ in range(8):
        assert draw(client, 2).json()['question']['chapter'] == 2


def test_missing_rules_fails_closed(practice_bank, monkeypatch, tmp_path):
    client, _ = practice_bank
    monkeypatch.setattr(service, 'RULES_PATH', tmp_path / 'missing.json')
    assert client.get('/api/chapter-bank/practice/chapters').json()[0]['available'] == 0
    assert draw(client).status_code == 404


def test_unordered_blanks_require_one_to_one_matching(practice_bank):
    client, _ = practice_bank
    rules = json.loads(service.RULES_PATH.read_text(encoding='utf-8'))
    next(r for r in rules['questions'] if r['id'] == 'cell')['unordered'] = True
    service.RULES_PATH.write_text(json.dumps(rules), encoding='utf-8')
    attempt = draw_question(client, 'cell')
    assert attempt['question']['blank_count'] == 2
    response = client.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit", json={'answer': ['闭塞', '两']})
    assert response.json()['feedback']['correct'] is True
    assert response.json()['feedback']['blank_results'] == [True, True]
    duplicate = draw_question(client, 'cell')
    response = client.post(f"/api/chapter-bank/practice/attempts/{duplicate['id']}/submit", json={'answer': ['两', '二']})
    assert response.json()['feedback']['correct'] is False
    assert sum(response.json()['feedback']['blank_results']) == 1


def test_compact_source_multi_answer_is_decoded_but_preserved_in_feedback(practice_bank, db_session):
    client, _ = practice_bank
    row = db_session.get(ChapterBankQuestion, 'multi')
    row.content = {**row.content, 'answer': 'AC'}
    db_session.commit()
    rules = json.loads(service.RULES_PATH.read_text(encoding='utf-8'))
    q = row.content
    signature = hashlib.sha256(json.dumps({k: q.get(k) for k in
        ('id', 'chapter', 'kind', 'stem', 'options', 'answer', 'answer_status')},
        ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    next(r for r in rules['questions'] if r['id'] == 'multi')['signature'] = signature
    service.RULES_PATH.write_text(json.dumps(rules), encoding='utf-8')
    attempt = draw_question(client, 'multi')
    assert attempt['question']['id'] == 'multi'
    response = client.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit", json={'answer': ['C', 'A']})
    assert response.json()['feedback']['correct'] is True
    assert response.json()['feedback']['correct_answer'] == 'AC'


def test_unreviewed_media_never_enters_pool(practice_bank, db_session):
    client, _ = practice_bank
    row = db_session.get(ChapterBankQuestion, 'choice')
    row.content = {**row.content, 'media_review_required': True}
    db_session.commit()
    assert client.get('/api/chapter-bank/practice/chapters').json()[0]['available'] == 1


@pytest.mark.parametrize('answer', ['x' * 1001, ['x' * 1001], ['x'] * 21])
def test_submission_transport_rejects_oversized_payload_even_on_retry(practice_bank, answer):
    client, _ = practice_bank
    attempt = draw_question(client, 'bool')
    url = f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit"
    assert client.post(url, json={'answer': False}).status_code == 200
    assert client.post(url, json={'answer': answer}).status_code == 422
