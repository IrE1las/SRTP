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
    assert [r['objective'] for r in rows] == [12, 12, 12, 12, 12, 12]
    assert sum(r['essay'] for r in rows) == 0
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
    assert question_list(db_session, 1, kind='essay')['total'] == 0
    pending = question_list(db_session, 4, status='pending', kind='all', limit=100)
    assert pending['total'] == 0
    assert question_list(db_session, kind='all', limit=100)['total'] == 182
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


def test_182_question_scope_is_identical_for_students_teachers_and_direct_links(client, db_session):
    from app.api.deps import get_current_user
    from main import app
    bank=load_bank()
    import_bank(db_session,bank);db_session.commit()
    original={row.id:row.content for row in db_session.query(ChapterBankQuestion)}
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id=1,role='student')
    first=client.get('/api/chapter-bank/questions?limit=100').json()
    second=client.get('/api/chapter-bank/questions?limit=100&page=2').json()
    ids={q['id'] for q in first['items']+second['items']}
    assert first['total']==second['total']==len(ids)==182
    assert [q['objective'] for q in client.get('/api/chapter-bank/chapters').json()]==[31,28,29,36,32,26]
    assert [q['total_objective'] for q in client.get('/api/chapter-bank/practice/chapters').json()]==[31,28,29,36,32,26]
    assert all(q['can_practice'] and 'answer' not in q for q in first['items']+second['items'])
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id=1,role='teacher')
    managed=client.get('/api/chapter-bank/manage/questions?limit=100').json()
    managed2=client.get('/api/chapter-bank/manage/questions?limit=100&page=2').json()
    assert managed['total']==managed2['total']==182
    assert {q['id'] for q in managed['items']+managed2['items']}==ids
    for hidden in ['C1-005','C3-008','W-008']:
        assert hidden not in ids
        assert client.get('/api/chapter-bank/manage/questions/'+hidden).status_code==404
        assert client.get('/api/chapter-bank/questions/'+hidden+'/reference').status_code==404
    assert {row.id:row.content for row in db_session.query(ChapterBankQuestion)}==original
