"""Own-answer paging and detail access for the second S1 acceptance correction."""
from datetime import datetime
import pytest
from app.models import LabQuestion,LabAttempt,User
from app.services.bootstrap import seed_theory
from app.services.lab_topics import evaluate
from tests.helpers import auth_headers
from tests.test_lab_topics import completed

@pytest.fixture()
def people(client,db_session):
    seed_theory(db_session)
    tokens={name:auth_headers(client,'r2_'+name,'student' if name!='teacher' else 'teacher')
            for name in ['owner','other','teacher']}
    users={name:db_session.query(User).filter_by(username='r2_'+name).one() for name in tokens}
    return tokens,users

def make_attempts(db,user,count=1,key='lab-01-01'):
    q=db.query(LabQuestion).filter_by(key=key).one()
    answers=completed(q)
    rows=[LabAttempt(question_id=q.id,student_id=user.id,question_snapshot=q.content,answers=answers,
                     result=evaluate(q.content,answers),created_at=datetime(2026,10,27,0,0,0)) for _ in range(count)]
    db.add_all(rows);db.commit()
    return rows

def test_six_item_server_pages_are_stable_owner_scoped_and_not_truncated_at_200(client,people,db_session):
    auth,users=people
    rows=make_attempts(db_session,users['owner'],205)
    make_attempts(db_session,users['owner'],1,'lab-02-01')
    make_attempts(db_session,users['other'],3)
    def page(number):
        response=client.get('/api/lab-topics/attempts/page',headers=auth['owner'],params={'topic':1,'page':number})
        assert response.status_code==200,response.text
        assert '"answers"' not in response.text and '"feedback"' not in response.text and '"expected"' not in response.text
        return response.json()
    first,second,last=page(1),page(2),page(35)
    assert first['total']==205 and first['page_count']==35 and first['page_size']==6
    assert len(first['items'])==len(second['items'])==6 and len(last['items'])==1
    assert [a['id'] for a in first['items']]==[row.id for row in rows[-6:][::-1]]
    assert not set(a['id'] for a in first['items'])&set(a['id'] for a in second['items'])
    assert last['items'][0]['id']==rows[0].id
    assert page(999)['page']==35
    assert all(item['topic']==1 for item in first['items']+last['items'])

def test_detail_is_loaded_separately_and_only_by_its_owner(client,people,db_session):
    auth,users=people
    attempt=make_attempts(db_session,users['owner'])[0]
    path='/api/lab-topics/attempts/'+str(attempt.id)
    response=client.get(path,headers=auth['owner'])
    assert response.status_code==200
    assert response.json()['answers']==attempt.answers
    assert response.json()['result']['feedback']==attempt.result['feedback']
    assert client.get(path,headers=auth['other']).status_code==404
    assert client.get(path,headers=auth['teacher']).status_code==404
    assert client.get(path).status_code==401
    assert client.get('/api/lab-topics/attempts/999999',headers=auth['owner']).status_code==404

@pytest.mark.parametrize('params',[{'topic':7},{'topic':1,'page':0},{'topic':1,'page':-2},{'topic':1,'page_size':7}])
def test_invalid_paging_requests_are_rejected(client,people,params):
    auth,_=people
    assert client.get('/api/lab-topics/attempts/page',headers=auth['owner'],params=params).status_code==422

def test_empty_page_has_truthful_zero_total_and_no_fake_records(client,people):
    auth,_=people
    response=client.get('/api/lab-topics/attempts/page',headers=auth['owner'],params={'topic':1,'page':88})
    assert response.json()=={'items':[],'total':0,'page':1,'page_size':6,'page_count':1}
    assert client.get('/api/lab-topics/attempts/page',params={'topic':1}).status_code==401
