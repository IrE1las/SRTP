from types import SimpleNamespace
import pytest

from app.models.chapter_bank import ChapterBankQuestion
from app.services.chapter_bank import import_bank, load_bank, chapters, question_list


def test_import_repeat_and_source_classification(db_session):
    bank = {'questions': [q for q in load_bank()['questions'] if not q.get('batch', '').startswith('2026-11-11')]}
    assert len(bank['questions']) == 298
    result = import_bank(db_session, bank)
    assert result['created'] == 298
    assert import_bank(db_session, bank)['created'] == 0
    assert db_session.query(ChapterBankQuestion).count() == 298
    rows = chapters(db_session)
    assert [r['objective'] for r in rows] == [53, 28, 27, 71, 27, 50]
    assert sum(r['essay'] for r in rows) == 42
    for ch in range(1, 7):
        listing = question_list(db_session, ch, kind='all', limit=100)
        assert listing['total'] == next(r['total'] for r in rows if r['id'] == ch)
        assert all(q['chapter'] == ch for q in listing['items'])
        assert all('answer' not in q and 'partial_answer' not in q for q in listing['items'])


def test_filters_and_invalid_import_are_atomic(db_session):
    bank = load_bank()
    bad = {**bank, 'questions': [bank['questions'][0], {**bank['questions'][1], 'chapter': 99}]}
    with pytest.raises(ValueError):
        import_bank(db_session, bad)
    assert db_session.query(ChapterBankQuestion).count() == 0
    import_bank(db_session, bank)
    assert question_list(db_session, 1, kind='essay')['total'] == 26
    pending = question_list(db_session, 4, status='pending', kind='all', limit=100)
    assert all(q['answer_status'] in ('pending', 'partial', 'platform_answer') for q in pending['items'])
    assert question_list(db_session, 6, search='no-such-question')['total'] == 0
    assert question_list(db_session, 6, kind='all', page=99)['items'] == []


def test_api_auth_and_answer_permissions(client, db_session):
    from app.api.deps import get_current_user
    from main import app
    import_bank(db_session, load_bank())
    assert client.get('/api/chapter-bank/chapters').status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='student')
    assert client.get('/api/chapter-bank/chapters').status_code == 200
    assert client.get('/api/chapter-bank/chapters/7/questions').status_code == 422
    assert client.get('/api/chapter-bank/chapters/1/questions?limit=101').status_code == 422
    listing = client.get('/api/chapter-bank/chapters/1/questions').json()
    qid = listing['items'][0]['id']
    assert client.get(f'/api/chapter-bank/questions/{qid}/reference').status_code == 403
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='teacher')
    assert client.get(f'/api/chapter-bank/questions/{qid}/reference').status_code == 200
    assert client.get('/api/chapter-bank/questions/missing/reference').status_code == 404
