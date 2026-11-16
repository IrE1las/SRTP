from types import SimpleNamespace
import pytest
from main import app
from app.api.deps import get_current_user
from app.models.chapter_bank import ChapterBankQuestion
from app.services.chapter_bank import import_bank, load_bank

ROOT = '/api/chapter-bank/manage/questions'


@pytest.fixture()
def manager(client):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='teacher')
    return client


def body(**values):
    return {'chapter': 1, 'kind': 'choice', 'stem': '教师编写的题目', 'options': ['甲', '乙'],
            'answer': 'B', 'source_reference': '教师依据教材第3页核对', **values}


def create(client, **values):
    response = client.post(ROOT, json=body(**values))
    assert response.status_code == 201, response.text
    return response.json()


def test_student_cannot_read_or_mutate_management_answers(manager):
    q = create(manager)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role='student')
    assert manager.get(ROOT).status_code == 403
    assert manager.get(ROOT+'/'+q['id']).status_code == 403
    assert manager.post(ROOT, json=body()).status_code == 403
    assert manager.put(ROOT+'/'+q['id'], json=body(revision=1)).status_code == 403
    assert manager.delete(ROOT+'/'+q['id']+'?revision=1').status_code == 403
    public = manager.get('/api/chapter-bank/questions',params={'search':'教师编写的题目'}).json()['items'][0]
    assert public['can_practice'] is True
    assert all(key not in public for key in ['answer','accepted','explanation','_practice_rule'])


@pytest.mark.parametrize('values,answer', [
    ({}, 'B'),
    ({'kind':'multi','options':['甲','乙','丙'],'answer':['A','C']}, ['C','A']),
    ({'kind':'true_false','options':[],'answer':False}, False),
    ({'kind':'cell','options':[],'answer':['锁闭','2'],'accepted':[['锁闭','锁 闭'],['二']]}, ['锁闭','二']),
])
def test_teacher_answers_feed_real_student_practice(manager, db_session, values, answer):
    q = create(manager, **values)
    assert q['can_practice'] is True
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role='student')
    excludes=[row.id for row in db_session.query(ChapterBankQuestion) if row.id != q['id']]
    attempt = manager.post('/api/chapter-bank/practice/chapters/1/draw',json={'exclude_ids':excludes}).json()
    assert attempt['question']['id'] == q['id']
    assert 'answer' not in attempt['question'] and attempt['feedback'] is None
    submitted = manager.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit",json={'answer':answer})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()['feedback']['correct'] is True


@pytest.mark.parametrize('values', [
    {'stem':' '}, {'source_reference':' '}, {'answer':False}, {'answer':'C'},
    {'options':['甲',' ']}, {'kind':'multi','answer':['A','A']},
    {'kind':'true_false','answer':'false'}, {'kind':'cell','answer':['']},
    {'kind':'cell','answer':['甲','乙'],'accepted':[['甲']]},
])
def test_invalid_teacher_answer_never_authorizes_grading(manager, db_session, values):
    before = db_session.query(ChapterBankQuestion).count()
    assert manager.post(ROOT,json=body(**values)).status_code == 422
    assert db_session.query(ChapterBankQuestion).count() == before


def test_edit_conflict_and_delete_preserve_issued_attempts(manager, db_session):
    q = create(manager)
    # Exclude the reviewed source bank so the test draws only its new question.
    excludes=[row.id for row in db_session.query(ChapterBankQuestion) if row.id != q['id']]
    attempt=manager.post('/api/chapter-bank/practice/chapters/1/draw',json={'exclude_ids':excludes}).json()
    updated=manager.put(ROOT+'/'+q['id'],json=body(answer='A',revision=1))
    assert updated.status_code == 200 and updated.json()['revision'] == 2
    assert manager.put(ROOT+'/'+q['id'],json=body(revision=1)).status_code == 409
    assert manager.delete(ROOT+'/'+q['id']+'?revision=1').status_code == 409
    assert manager.delete(ROOT+'/'+q['id']+'?revision=2').status_code == 200
    assert manager.get(ROOT+'/'+q['id']).status_code == 404
    assert manager.get('/api/chapter-bank/questions',params={'search':'教师编写的题目'}).json()['total'] == 0
    assert manager.put('/api/chapter-bank/practice/bookmarks/'+q['id'],json={'marked':True}).status_code == 404
    submitted=manager.post(f"/api/chapter-bank/practice/attempts/{attempt['id']}/submit",json={'answer':'B'})
    assert submitted.json()['feedback']['correct'] is True
    assert db_session.get(ChapterBankQuestion,q['id']).content['_deleted'] is True


def test_deleted_imported_question_stays_deleted_after_reimport(manager, db_session):
    bank=load_bank()
    import_bank(db_session,bank);db_session.commit()
    from app.services.chapter_bank import question_list
    qid=question_list(db_session)['items'][0]['id']
    row=next(q for q in bank['questions'] if q['id']==qid)
    assert manager.delete(ROOT+'/'+row['id']+'?revision=0').status_code == 200
    import_bank(db_session,bank);db_session.commit()
    assert manager.get(ROOT+'/'+row['id']).status_code == 404
    assert manager.get('/api/chapter-bank/questions/'+row['id']+'/reference').status_code == 404
    assert manager.get('/api/chapter-bank/questions',params={'limit':100}).json()['total'] == 181


def test_unverified_source_blank_is_hidden_from_all_live_views_but_data_is_retained(manager, db_session):
    db_session.add(ChapterBankQuestion(id='unverified-blank',chapter=1,kind='cell',answer_status='pending',
        content={'id':'unverified-blank','chapter':1,'kind':'cell','answer_status':'pending','stem':'资料缺少答案的填空',
                 'answer':None,'source_reference':'原资料','images':['images/fig1-5.png']}))
    db_session.commit()
    response=manager.get(ROOT+'/unverified-blank')
    assert response.status_code==404
    assert manager.get('/api/chapter-bank/questions/unverified-blank/reference').status_code==404
    assert manager.get(ROOT,params={'search':'资料缺少答案'}).json()['total']==0
    assert manager.get('/api/chapter-bank/questions',params={'search':'资料缺少答案'}).json()['total']==0
    assert manager.put('/api/chapter-bank/practice/bookmarks/unverified-blank',json={'marked':True}).status_code==404
    retained=db_session.get(ChapterBankQuestion,'unverified-blank')
    assert retained.content['answer'] is None and retained.content['images']==['images/fig1-5.png']
