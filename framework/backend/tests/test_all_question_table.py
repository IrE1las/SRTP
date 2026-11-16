"""Complete browsing uses current-account, ever-correct history without answer leaks."""
from types import SimpleNamespace
from app.api.deps import get_current_user
from app.services import chapter_bank
from tests.test_chapter_practice import practice_client, practice_bank, draw


def choice_attempt(client):
    response=draw(client,exclude_ids=['multi'])
    assert response.status_code==200
    assert response.json()['question']['id']=='choice'
    return response.json()['id']


def table(client,**params):
    response=client.get('/api/chapter-bank/questions',params=params)
    assert response.status_code==200,response.text
    return response.json()


def test_ever_correct_survives_later_mistakes_but_never_crosses_accounts(practice_bank):
    client,app=practice_bank
    for answer in ['A','B','A']:
        attempt=choice_attempt(client)
        assert client.post('/api/chapter-bank/practice/attempts/'+attempt+'/submit',json={'answer':answer}).status_code==200
    row=next(q for q in table(client)['items'] if q['id']=='choice')
    assert row['ever_correct'] is True and row['attempted'] is True
    assert table(client,progress='correct')['total']==1
    assert table(client,progress='not_correct')['total']==3
    assert not any(key in row for key in ('answer','feedback','correct_answer','answer_evidence'))
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id=2,role='student')
    row=next(q for q in table(client)['items'] if q['id']=='choice')
    assert row['ever_correct'] is False and row['attempted'] is False
    assert table(client,progress='correct')['total']==0


def test_only_graded_questions_are_visible_and_pagination_filters_are_complete(practice_bank):
    client,_=practice_bank
    data=table(client)
    assert data['total']==4
    assert {q['id'] for q in data['items']}=={'choice','multi','bool','cell'}
    assert all(q['can_practice'] for q in data['items'])
    assert table(client,chapter=2,kind='true_false')['total']==1
    first,second=table(client,limit=2),table(client,limit=2,page=2)
    assert first['total']==second['total']==4
    assert len(first['items'])==len(second['items'])==2
    assert not ({q['id'] for q in first['items']} & {q['id'] for q in second['items']})


def test_complete_bank_only_exposes_182_ready_questions_while_retaining_source_rows(db_session):
    chapter_bank.import_bank(db_session,chapter_bank.load_bank())
    data=chapter_bank.question_list(db_session,user_id=11,limit=100)
    assert data['total']==182
    assert all(q['kind']!='essay' for q in data['items'])
    assert all('answer' not in q for q in data['items'])
    assert all(q['can_practice'] for q in data['items'])
    from app.models.chapter_bank import ChapterBankQuestion
    assert db_session.query(ChapterBankQuestion).count()==408


def test_all_question_table_requires_authentication(practice_client):
    client,_=practice_client
    assert client.get('/api/chapter-bank/questions').status_code==401
