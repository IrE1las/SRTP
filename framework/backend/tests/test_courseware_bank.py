from collections import Counter

from app.models.chapter_bank import ChapterBankQuestion
from app.services.chapter_bank import import_bank, load_bank


def test_courseware_questions_have_supported_answers_and_balanced_types():
    items = [q for q in load_bank()['questions'] if q['id'].startswith('PPT-')]
    assert len(items) == 72
    assert Counter((q['chapter'], q['kind']) for q in items) == {
        (chapter, kind): 4 for chapter in range(1, 7) for kind in ('cell', 'choice', 'true_false')
    }
    assert len({q['id'] for q in items}) == len(items)
    assert len({q['stem'] for q in items}) == len(items)
    for q in items:
        assert q['answer_status'] == 'material_supported'
        assert q['source_excerpt'] and q['answer_evidence'] and q['explanation']
        assert q['source_file'].endswith(('.ppt', '.pdf')) and q['source_page'] > 0
        assert q['publication_status'] == 'draft' and q['auto_score_ready'] is False
        if q['kind'] == 'choice':
            assert [o['key'] for o in q['options']] == list('ABCD')
            assert len({o['text'] for o in q['options']}) == 4
            assert q['answer'] in 'ABCD' and len(q['answer']) == 1
        elif q['kind'] == 'true_false':
            assert type(q['answer']) is bool
        else:
            assert isinstance(q['answer'], (str, list)) and q['answer']


def test_append_courseware_preserves_existing_content(db_session):
    bank = {'questions': [q for q in load_bank()['questions'] if not q.get('batch', '').startswith('2026-11-11')]}
    old = [q for q in bank['questions'] if q.get('source_kind') != 'courseware_adapted']
    assert len(old) == 226
    assert import_bank(db_session, {'questions': old})['created'] == 226
    row = db_session.get(ChapterBankQuestion, old[0]['id'])
    edited = {**row.content, 'stem': 'Teacher revised this local question.'}
    row.content = edited
    db_session.flush()
    assert import_bank(db_session, bank) == {'created': 72, 'skipped': 226}
    assert row.content == edited
    assert import_bank(db_session, bank) == {'created': 0, 'skipped': 298}
