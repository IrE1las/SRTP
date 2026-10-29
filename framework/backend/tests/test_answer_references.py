import copy
import json

import pytest

from app.services import lab_topics
from app.services.answer_references import load_references, explanation_text
from app.models import LabQuestion
from tests.test_lab_topics import topics, completed


def test_all_manual_fields_have_supported_or_explicitly_limited_references(topics):
    refs = load_references(lab_topics.ROOT)
    manual = [(q.key, f) for q in topics for f in q.content['fields'] if f['kind']=='essay']
    assert len(manual) == len(refs) == 35
    for key, field in manual:
        assert 'expected' not in field
        assert field['explanation'] == explanation_text(refs[(key, field['id'])])
    assert all(key[0] in lab_topics.RETAINED_KEYS for key in refs)


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
