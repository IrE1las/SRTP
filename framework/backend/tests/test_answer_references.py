import copy
import json

import pytest

from app.services import lab_topics
from app.services.answer_references import load_references, explanation_text
from app.models import LabQuestion
from tests.test_lab_topics import topics, completed
from tests.test_management import setup, content, create, publish, submit


def test_all_manual_fields_have_supported_or_explicitly_limited_references(topics):
    refs = load_references(lab_topics.ROOT)
    manual = [(q.key, f) for q in topics for f in q.content['fields'] if f['kind']=='essay']
    assert len(manual) == len(refs) == 50
    for key, field in manual:
        assert 'expected' not in field
        assert field['explanation'] == explanation_text(refs[(key, field['id'])])
    low_frequency = next(q for q in topics if q.key == 'lab-08-03')
    for f in low_frequency.content['fields']:
        assert refs[(low_frequency.key, f['id'])]['status'] == 'missing'
        assert '暂不能确定' in f['explanation']
        assert '不将任何猜测映射作为标准评分依据' in f['explanation']


def test_reference_hidden_before_submission_visible_after_but_never_auto_scores_essay(topics):
    for q in topics:
        public = lab_topics.public_question(q)
        assert all('explanation' not in f for f in public['fields'])
        result = lab_topics.evaluate(q.content, completed(q))
        assert result['status']=='pending_review' and result['total_score'] is None
        for f in result['feedback']:
            if f['status']=='pending_review':
                assert f['explanation'] and 'points' not in f


def test_reference_source_mutation_rejected(tmp_path):
    folder = tmp_path/'ai_design/station'
    folder.mkdir(parents=True)
    data = {'version':1,'sources':[{'path':'changed.txt','sha256':'0'*64}],'entries':[]}
    (folder/'report_answer_references.json').write_text(json.dumps(data),encoding='utf8')
    (tmp_path/'changed.txt').write_text('Changed source',encoding='utf8')
    with pytest.raises(ValueError,match='参考答案依据已变化'):
        load_references(tmp_path)


def test_admin_can_edit_reference_without_changing_old_submission(client, setup, db_session):
    raw = content()
    raw['fields'][-1]['explanation'] = '参考解答：须结合给定的道岔锁闭状态。'
    q = client.post('/api/management/questions',headers=setup['admin'],json={'content':raw}).json()
    live = publish(client,setup['admin'],q)
    old_attempt = submit(client,setup['student'],q['key'])
    feedback = next(f for f in old_attempt['result']['feedback'] if f['status']=='pending_review')
    assert feedback['explanation'] == raw['fields'][-1]['explanation']
    raw['fields'][-1]['explanation'] = '新版参考解答：补充资料核对说明。'
    draft = client.put(f"/api/management/questions/{q['id']}/draft",headers=setup['admin'],
        json={'revision':live['revision'],'content':raw})
    assert draft.status_code==200, draft.text
    publish(client,setup['admin'],draft.json())
    public = client.get('/api/lab-topics/questions/'+q['key'],headers=setup['student']).json()
    assert 'explanation' not in public['fields'][-1]
    detail = client.get(f"/api/management/reviews/{old_attempt['id']}",headers=setup['teacher']).json()
    assert detail['question']['fields'][-1]['explanation']==feedback['explanation']
