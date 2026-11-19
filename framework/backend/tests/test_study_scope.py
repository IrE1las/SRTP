"""Only six topics and the standard station remain; free practice writes no records."""
from copy import deepcopy
from contextlib import closing
import sqlite3
from sqlalchemy import inspect,select,func,text
from app.core.database import Base
from app.models import LabQuestion,LabAttempt
from app.services.study_scope import retire_study_scope,REMOVED_TABLES
from tests.test_exercise_api import auth_headers
from tests.test_lab_topics import topics,completed


def test_standard_only_free_console_never_writes_experiment_records(client,db_session):
    auth=auth_headers(client,'free_scope_student','student')
    other=auth_headers(client,'other_scope_student','student')
    root='/api/simulation-console'
    before={t.name:db_session.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
    assert client.get(root+'/station?source=workbook',headers=auth).status_code==422
    assert client.post(root+'/sessions',headers=auth,json={'source':'workbook'}).status_code==422
    station=client.get(root+'/station',headers=auth).json()
    assert station['station_name']=='标准站' and station['profile']=='reference'
    snap=client.post(root+'/sessions',headers=auth,json={}).json()
    url=root+'/sessions/'+snap['session_id']
    changed=client.post(url+'/commands',headers=auth,json={'type':'SET_SECTION_OCCUPANCY','target':'IAG','payload':{'kind':'fault'},'version':snap['version']})
    assert changed.status_code==200 and changed.json()['accepted']
    assert client.get(url,headers=other).status_code==409
    assert client.get('/api/learning-records',headers=auth).json()['total']==0
    assert client.get('/api/learning-records/simulation/'+snap['session_id'],headers=auth).status_code==404
    after={t.name:db_session.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}
    assert before==after


def test_six_topics_use_the_right_station_and_question_sessions_are_isolated(client,topics):
    auth=auth_headers(client,'topic_scope_student','student')
    questions=client.get('/api/lab-topics/questions',headers=auth).json()
    assert len(questions)==34 and {q['topic'] for q in questions}==set(range(1,7))
    for topic in range(1,7):
        q=client.get(f'/api/lab-topics/questions/lab-{topic:02d}-01',headers=auth).json()
        assert q['diagram_mode']==('standard' if topic<=4 else 'station')
    base='/api/lab-topics/questions/'
    first=client.post(base+'lab-01-01/console/sessions',headers=auth,json={}).json()
    assert first['profile']=='reference'
    foreign=client.get(base+'lab-02-01/console/sessions/'+first['session_id'],headers=auth)
    assert foreign.status_code==409
    assert client.get(base+'lab-05-01/console/station',headers=auth).status_code==404
    assert client.get(base+'lab-07-01',headers=auth).status_code==404
    assert client.get('/api/modules',headers=auth).status_code==404
    assert client.post('/api/exam/submit',headers=auth,json={}).status_code==404


def test_standard_topic_content_matches_the_displayed_station(topics):
    from app.services.simulation_console.reference_station import reference_station_package
    package=reference_station_package()
    routes={r['name']:r for r in package['routes']}
    for name in ('D1>D5','D1>S4','D15>S4','SII>D1','SIII>D3','D13>SII','D3>D7','D3>D11','L_X>SI'):
        assert name in routes
    question=next(q for q in topics if q.key=='lab-01-02')
    fields={f['id']:f for f in question.content['fields']}
    assert fields['buttons']['expected']==','.join(routes['D1>D5']['button_sequence'])
    assert fields['sections']['expected']==','.join(routes['D1>D5']['sections'])
    assert fields['switches']['expected']=='1/3'
    assert all(q.content['station_key']=='standard-station' for q in topics if q.topic<=4)
    assert all(q.content['station_key']=='original-photo-station' for q in topics if q.topic>=5)


def test_authoring_uses_the_same_standard_inventory_without_old_interval_requirement(client,topics):
    auth=auth_headers(client,'scope-author','admin')
    meta=client.get('/api/management/metadata',headers=auth).json()
    assert '22' in meta['standard_devices'] and '2/20WG' in meta['standard_devices']
    assert {t['id'] for t in meta['topics']}==set(range(1,7))
    payload={'topic':1,'title':'标准站录题','prompt':'观察22号道岔的状态。','devices':['22'],
             'source_section':'标准站配置与本机观察','conditions':[],'fields':[
                 {'id':'reason','kind':'essay','label':'记录条件和现象','points':10,'criteria':['记录依据']} ]}
    result=client.post('/api/management/preview',headers=auth,json={'content':payload})
    assert result.status_code==200,result.text
    assert result.json()['question']['station_key']=='standard-station'


def test_station_upgrade_versions_original_question_without_rewriting_answers(db_session,topics):
    from app.models import User,QuestionRevision,QuestionWorkspace
    from app.services.lab_topics import upgrade_standard_topics,digest
    from app.services.question_authoring import initialize_workspace
    question=topics[0]
    original=deepcopy(question.content)
    original['station_key']='original-photo-station'
    question.content=original
    question.fingerprint=digest(original)
    user=User(username='upgrade-owner',password_hash='fixture',role='student')
    db_session.add(user);db_session.flush()
    answer=LabAttempt(question_id=question.id,student_id=user.id,question_snapshot=deepcopy(original),answers=completed(question),result={})
    db_session.add(answer)
    protected=topics[1]
    protected.content={**deepcopy(protected.content),'authoring_source':'administrator'}
    protected.fingerprint='a'*64
    state=initialize_workspace(db_session,protected)
    state.draft=deepcopy(protected.content)
    db_session.commit()
    assert upgrade_standard_topics(db_session)==[question.key]
    db_session.commit();db_session.expire_all()
    assert question.content['station_key']=='standard-station'
    assert answer.question_snapshot==original
    assert db_session.get(QuestionWorkspace,question.id).published_version==2
    versions=db_session.query(QuestionRevision).filter_by(question_id=question.id).order_by(QuestionRevision.version).all()
    assert versions[0].content==original and versions[1].content==question.content
    assert protected.content['authoring_source']=='administrator' and state.draft is not None
    assert upgrade_standard_topics(db_session)==[]


def test_retirement_backs_up_removed_content_and_preserves_retained_answers(db_session,topics):
    from app.models.user import User
    user=User(username='retained-answer-owner',password_hash='fixture',role='student')
    db_session.add(user);db_session.flush()
    kept=topics[0]
    removed=LabQuestion(key='lab-07-01',dataset_id=kept.dataset_id,topic=7,sequence=1,content={**deepcopy(kept.content),'topic':7},fingerprint='x'*64)
    db_session.add(removed);db_session.flush()
    kept_answer=LabAttempt(question_id=kept.id,student_id=user.id,question_snapshot=deepcopy(kept.content),answers=completed(kept),result={})
    old_answer=LabAttempt(question_id=removed.id,student_id=user.id,question_snapshot=deepcopy(removed.content),answers={},result={})
    db_session.add_all([kept_answer,old_answer]);db_session.commit()
    kept_id=kept_answer.id
    with db_session.bind.begin() as db:
        for name in REMOVED_TABLES:db.execute(text(f'CREATE TABLE {name} (id INTEGER PRIMARY KEY)'))
    report=retire_study_scope(db_session.bind)
    try:
        assert report['removed_questions']==1 and report['backup'].is_file()
        assert not (set(REMOVED_TABLES) & set(inspect(db_session.bind).get_table_names()))
        db_session.expire_all()
        assert db_session.query(LabQuestion).count()==34
        assert db_session.query(LabAttempt).count()==1
        assert db_session.get(LabAttempt,kept_id).answers==completed(kept)
        with closing(sqlite3.connect(report['backup'])) as backup:
            assert backup.execute('SELECT count(*) FROM lab_questions').fetchone()[0]==35
        assert retire_study_scope(db_session.bind) is None
    finally:
        report['backup'].unlink()
