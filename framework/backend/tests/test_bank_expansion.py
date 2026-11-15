import json
from app.services.chapter_bank import BANK_PATH, load_bank, import_bank


def test_expansion_provenance_and_insert_only(db_session):
    manifest=json.loads((BANK_PATH.parent/'bank_expansion_20261111.json').read_text(encoding='utf-8'))
    bank=load_bank()
    incoming=[q for q in bank['questions'] if q['id'] in manifest['ids']]
    old=[q for q in bank['questions'] if q['id'] not in manifest['ids']]
    assert len(old)==298 and len(incoming)==manifest['count']
    assert len({q['stem'] for q in bank['questions']})==len(bank['questions'])
    for q in incoming:
        assert q['answer_evidence'] and q['source_reference'] and q['explanation']
        assert q['auto_score_ready'] is False and q['publication_status']=='draft'
        assert q['kind']!='essay' and q['answer'] is not None
    assert import_bank(db_session,{'questions':old})['created']==298
    assert import_bank(db_session,bank)=={'created':len(incoming),'skipped':298}
    assert import_bank(db_session,bank)['created']==0
