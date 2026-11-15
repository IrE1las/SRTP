import copy
import json

import pytest

from app.models.lab_topic import LabAttempt, LabQuestion
from app.models.shunting_route import ShuntingQuestion, ShuntingRoute
from app.services import lab_topics
from tests.test_exercise_api import auth_headers
from tests.test_shunting_questions import _import_payload


@pytest.fixture()
def topics(db_session):
    _import_payload(db_session)
    lab_topics.import_topics(db_session)
    db_session.commit()
    return db_session.query(LabQuestion).order_by(LabQuestion.key).all()


def completed(question):
    return {f['id']:copy.deepcopy(f.get('expected','测试用实验记录：条件、现象及依据。')) for f in question.content['fields']}


def test_report_coverage_and_source_binding(topics, db_session):
    assert len(topics)==24
    assert {q.topic for q in topics}==set(range(1,9))
    assert all(sum(q.topic==topic for q in topics)==3 for topic in range(1,9))
    assert db_session.query(ShuntingRoute).count()==35
    assert db_session.query(ShuntingQuestion).count()==0
    shunting=db_session.query(ShuntingRoute).filter_by(route_number=34).one()
    q=next(q for q in topics if q.key=='lab-06-02')
    field=next(f for f in q.content['fields'] if f['id']=='switches')
    assert field['expected']==shunting.fields['道岔']=='(17/19)、{23/25}、27'
    assert all(q.content['conditions'] for q in topics if q.topic>=7)


def test_all_authored_questions_evaluate_without_invented_manual_score(topics):
    for q in topics:
        result=lab_topics.evaluate(q.content,completed(q))
        assert result['automatic_score']==result['automatic_max']
        assert result['manual_max']>0
        assert result['status']=='pending_review'
        assert result['total_score'] is None


def test_public_payload_has_no_answers_or_rubric(topics):
    for q in topics:
        item=lab_topics.public_question(q)
        for f in item['fields']:
            assert not set(f)&{'expected','expected_runs','criteria','binding','explanation'}
        assert 'content' not in item
        assert 'fields' not in lab_topics.public_question(q,detail=False)


def test_cell_normalization_preserves_semantic_brackets(topics):
    q=next(q for q in topics if q.key=='lab-06-02')
    answers=completed(q)
    answers['switches']='27，｛23/25｝， （17/19）'
    assert lab_topics.evaluate(q.content,answers)['automatic_score']==40
    for wrong in ['27,[23/25],(17/19)','27,23/25,(17/19)','27,|23/25|,(17/19)']:
        answers['switches']=wrong
        item=next(f for f in lab_topics.evaluate(q.content,answers)['feedback'] if f['id']=='switches')
        assert item['status']=='incorrect'
        assert item['errors']
        assert '{23/25}' in item['expected']


def test_conditional_check_cannot_be_dropped(topics):
    q=next(q for q in topics if q.key=='lab-06-03')
    answers=completed(q)
    answers['sections']='1DG、3DG、5DG'
    feedback=lab_topics.evaluate(q.content,answers)['feedback']
    field=next(f for f in feedback if f['id']=='sections')
    assert field['status']=='incorrect'
    assert any('<5/7>5DG' in e for e in field['errors'])


def test_start_and_end_button_order_cannot_be_reversed(topics):
    q=next(q for q in topics if q.key=='lab-06-02')
    answers=completed(q)
    answers['buttons']='SIIDA、D13A'
    field=next(f for f in lab_topics.evaluate(q.content,answers)['feedback'] if f['id']=='buttons')
    assert field['status']=='incorrect'
    assert '顺序' in field['errors'][0]


@pytest.mark.parametrize('change', ['missing','extra','blank','invalid_choice','oversized','wrong_type'])
def test_malformed_submission_is_rejected(topics, change):
    q=topics[0]
    answers=completed(q)
    if change=='missing': answers.pop('free')
    elif change=='extra': answers['client_score']=100
    elif change=='blank': answers['reason']=' '
    elif change=='invalid_choice': answers['free']='不在选项中'
    elif change=='oversized': answers['reason']='字'*6001
    else: answers['reason']={'expected':'能转换'}
    with pytest.raises(ValueError): lab_topics.evaluate(q.content,answers)


def test_order_and_multi_are_checked_exactly(topics):
    q=next(q for q in topics if q.key=='lab-03-01')
    answers=completed(q)
    answers['sequence'].reverse()
    assert lab_topics.evaluate(q.content,answers)['automatic_score']==0
    answers['sequence']=['车列进入5DG']
    with pytest.raises(ValueError): lab_topics.evaluate(q.content,answers)
    q=next(q for q in topics if q.key=='lab-05-03')
    field=next(f for f in q.content['fields'] if f['kind']=='multi')
    answers=completed(q)
    answers[field['id']]=field['options']
    assert lab_topics.evaluate(q.content,answers)['automatic_score']==0
    answers[field['id']]=[field['options'][0]]*2
    with pytest.raises(ValueError): lab_topics.evaluate(q.content,answers)


def test_import_is_idempotent_and_does_not_generate_old_questions(topics,db_session):
    assert lab_topics.import_topics(db_session)=={'topics':8,'total':24,'inserted':0,'updated':0}
    assert db_session.query(ShuntingQuestion).count()==0


def test_source_mutation_rejected(topics,db_session,tmp_path,monkeypatch):
    blueprint=json.loads(lab_topics.BLUEPRINT.read_text(encoding='utf-8'))
    blueprint['reports'][0]['sha256']='0'*64
    changed=tmp_path/'changed.json'
    changed.write_text(json.dumps(blueprint,ensure_ascii=False),encoding='utf-8')
    monkeypatch.setattr(lab_topics,'BLUEPRINT',changed)
    with pytest.raises(ValueError,match='实验报告已变化'): lab_topics.resolve_blueprint(db_session)


def test_student_submit_teacher_review_and_history_isolation(client,topics,db_session,monkeypatch):
    student=auth_headers(client,'lab_student','student')
    other=auth_headers(client,'lab_other','student')
    teacher=auth_headers(client,'lab_teacher','teacher')
    q=topics[0]
    path=f'/api/lab-topics/questions/{q.key}'
    assert client.get('/api/lab-topics/questions').status_code==401
    assert len(client.get('/api/lab-topics/questions',headers=student).json())==24
    assert 'expected' not in client.get(path,headers=student).text
    assert client.get(path+'/rubric',headers=student).status_code==403
    assert client.get('/api/lab-topics/reviews',headers=student).status_code==403
    assert client.get(path+'/rubric',headers=teacher).status_code==200
    body={'fingerprint':'0'*64,'answers':completed(q)}
    assert client.post(path+'/submit',headers=student,json=body).status_code==409
    body['fingerprint']=q.fingerprint
    response=client.post(path+'/submit',headers=student,json=body)
    assert response.status_code==201,response.text
    attempt=response.json()
    assert attempt['result']['total_score'] is None
    assert client.get('/api/lab-topics/attempts',headers=other).json()==[]
    assert len(client.get('/api/lab-topics/attempts',headers=student).json())==1
    markpath=f"/api/lab-topics/attempts/{attempt['id']}/review"
    mark={'scores':{'reason':8},'comment':'解释准确，补充封闭对选路的限制。'}
    assert client.post(markpath,headers=student,json=mark).status_code==403
    assert client.post(markpath,headers=teacher,json={**mark,'scores':{'reason':11}}).status_code==422
    assert client.post(markpath,headers=teacher,json={**mark,'scores':{'reason':True}}).status_code==422
    assert client.post(markpath,headers=teacher,json={**mark,'comment':' '}).status_code==422
    marked=client.post(markpath,headers=teacher,json=mark)
    assert marked.status_code==200,marked.text
    assert marked.json()['result']['total_score']==48
    assert client.post(markpath,headers=teacher,json=mark).status_code==409
    saved=client.get('/api/lab-topics/attempts',headers=student).json()[0]
    assert saved['review']==mark
    assert saved['result']['status']=='graded'
    assert lab_topics.import_topics(db_session)['updated']==0
    dataset,items=lab_topics.resolve_blueprint(db_session)
    items[0]['prompt']='更改过的题目'
    monkeypatch.setattr(lab_topics,'resolve_blueprint',lambda db:(dataset,items))
    with pytest.raises(ValueError,match='已有作答'): lab_topics.import_topics(db_session)
    assert db_session.get(LabAttempt,attempt['id']).question_snapshot['prompt']!=items[0]['prompt']
