import hashlib
import json
from collections import Counter
from app.services.chapter_bank import BANK_PATH, load_bank


def test_practice_rules_are_pinned_to_reviewed_answer_and_stem():
    source={q['id']:q for q in load_bank()['questions']}
    entries=json.loads((BANK_PATH.parent/'chapter_practice_rules.json').read_text(encoding='utf-8'))['questions']
    assert len(entries)==182 and len({r['id'] for r in entries})==182
    assert Counter(source[r['id']]['chapter'] for r in entries)=={1:31,2:28,3:29,4:36,5:32,6:26}
    for r in entries:
        q=source[r['id']]
        assert not q.get('images') and q['answer_status'] in ('material_supported','exam_answer_key')
        signature=hashlib.sha256(json.dumps({k:q.get(k) for k in ('id','chapter','kind','stem','options','answer','answer_status')},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert r['signature']==signature
        if q['kind']=='cell':
            expected=q['answer'] if isinstance(q['answer'],list) else [q['answer']]
            assert [values[0] for values in r['accepted']]==expected
        assert q.get('auto_score_ready') is False  # Formal exercise grading remains separate.
