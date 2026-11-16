from tests.test_s5_exams import course, clock, publish, begin
from tests.helpers import auth_headers


def test_queue_only_shows_submitted_owned_exams_and_reuses_published_grades(client, course):
    roles, _, _ = course
    exam=publish(client,course)
    attempt=begin(client,roles,exam)
    assert client.get('/api/exams/reviews',headers=roles['teacher']).json()['total'] == 0
    sid=attempt['session_id']
    assert client.post(f'/api/exams/attempts/{sid}/submit',headers=roles['student'],json={'expected_sequence':0}).status_code == 200
    assert client.get('/api/exams/reviews',headers=roles['student']).status_code == 403
    other=auth_headers(client,'queue_other_teacher','teacher')
    assert client.get('/api/exams/reviews',headers=other).json()['total'] == 0
    assert client.get('/api/exams/reviews',headers=other,params={'exam_id':exam['id']}).status_code == 404
    listing=client.get('/api/exams/reviews',headers=roles['teacher']).json()
    assert listing['total']==1 and listing['items'][0]['session_id']==sid
    assert listing['counts']=={'all':1,'pending':1,'published':0}
    assert listing['items'][0]['identity']['real_name']=='s5_student'
    assert client.get('/api/exams/reviews',headers=roles['teacher'],params={'search':'no-match'}).json()['total']==0
    assert client.get('/api/exams/reviews',headers=roles['teacher'],params={'page':2}).json()['items']==[]
    grade=client.post(f'/api/exams/attempts/{sid}/grade/publish',headers=roles['teacher'],json={'revision':0,'score':0,'comment':'核对完成'})
    assert grade.status_code==200,grade.text
    assert client.get('/api/exams/reviews',headers=roles['teacher']).json()['total']==0
    released=client.get('/api/exams/reviews',headers=roles['teacher'],params={'status':'published'}).json()
    assert released['total']==1 and released['items'][0]['grade']['score']==0
    assert released['counts']=={'all':1,'pending':0,'published':1}
    assert client.get('/api/exams/reviews',headers=roles['admin'],params={'status':'all'}).json()['total']==1
