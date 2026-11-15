"""Student wording and figures must not change the source or grading contract."""
import copy
import re
from pathlib import Path

from app.services.chapter_bank import load_bank, import_bank, question_list
from app.services import chapter_practice as practice


def test_reviewed_questions_have_standalone_wording_without_source_preambles(db_session):
    bank = load_bank()
    original = copy.deepcopy(bank)
    import_bank(db_session, bank)
    reviewed = {r['id'] for r in practice.load_rules().values() if r}
    seen = {}
    for chapter in range(1, 7):
        seen.update({q['id']: q for q in question_list(db_session, chapter, limit=100)['items']})
    for qid in reviewed:
        assert not re.search(r'课件|讲义|该答案|该大纲|该题库|该论文|题库总序|按公开|该验收样表|该联锁功能检验记录', seen[qid]['stem']), qid
    assert seen['WEB11-018']['stem'].endswith('表示____。')
    assert '6502' in seen['CW11-001']['stem']
    assert '四线制' in seen['WEB11-003']['stem']
    assert bank == original
    assert len(practice.available_questions(db_session)) == 182


def test_draw_and_history_share_clean_wording_and_original_grading(db_session):
    bank = load_bank()
    q = next(q for q in bank['questions'] if q['id'] == 'PPT-PDF-002')
    original = copy.deepcopy(q)
    import_bank(db_session, {'questions': [q]})
    attempt = practice.draw(db_session, 1, 1, [], False)
    question = attempt['question']
    assert question['images'] == [{'src': '/chapter-bank/images/fig1-5.png', 'alt': '实例站场图1（图1-5）'}]
    assert '5/7' in question['stem']
    assert 'answer' not in question
    submitted = practice.submit(db_session, 1, attempt['id'], ['双动道岔'])
    assert submitted['feedback']['correct'] is True
    assert submitted['question'] == question
    assert practice.public_attempt(db_session, practice.get_attempt(db_session, 1, attempt['id']), 1)['question'] == question
    assert q == original


def test_source_figures_match_document_and_do_not_expose_answers(db_session):
    import_bank(db_session, load_bank())
    items = question_list(db_session, 1, limit=100)['items']
    question = next(q for q in items if q['id'] == 'C1-009')
    assert question['images'][0]['src'] == '/chapter-bank/images/fig1-5.png'
    assert 'answer' not in question
    root = Path(__file__).resolve().parents[3]
    for chapter in range(1, 7):
        for item in question_list(db_session, chapter, limit=100)['items']:
            for image in item['images']:
                asset = root / 'framework/frontend/public' / image['src'].lstrip('/')
                source = root / '题库整理/2026-11-02/images' / asset.name
                assert asset.read_bytes() == source.read_bytes()


def test_all_four_kinds_enter_one_uniform_random_pool(db_session, monkeypatch):
    import_bank(db_session, load_bank())
    # A captured real chapter pool proves there is no per-kind preselection/weighting.
    expected = {row.id for row, _ in practice.available_questions(db_session, 6)}
    assert {row.kind for row, _ in practice.available_questions(db_session, 6)} == {'choice', 'multi', 'cell', 'true_false'}
    class CaptureChoice:
        def choice(self, pool):
            assert len(pool) == len(expected)
            assert {row.id for row, _ in pool} == expected
            return pool[-1]
    monkeypatch.setattr(practice, 'RANDOM', CaptureChoice())
    assert practice.draw(db_session, 1, 6, [], False)['question']['chapter'] == 6


def test_local_edits_do_not_receive_stale_rewrites_or_added_figures():
    from app.services.chapter_bank_presentation import present_question
    question = copy.deepcopy(next(q for q in load_bank()['questions'] if q['id'] == 'PPT-PDF-002'))
    question['stem'] = '教师已修改的题干'
    assert present_question(question) == {'stem': question['stem'], 'images': []}


def test_teacher_image_replacement_takes_precedence_over_supplemental_figure():
    from app.services.chapter_bank_presentation import present_question
    question = copy.deepcopy(next(q for q in load_bank()['questions'] if q['id'] == 'PPT-PDF-002'))
    question['images'] = ['images/fig1-6.png']
    shown = present_question(question)
    # An illustration-specific rewrite must also stop referring to the old figure.
    assert shown == {'stem': question['stem'], 'images': [{'src': '/chapter-bank/images/fig1-6.png', 'alt': '实例站场图2（图1-6）'}]}
