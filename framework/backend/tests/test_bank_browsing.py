from app.services.chapter_bank import import_bank, chapters, question_list


def sample(qid, kind='choice', status='teacher_verified', **extra):
    from app.services.chapter_practice import signature
    value = dict(id=qid, chapter=1, kind=kind, answer_status=status, stem='Test stem '+qid,
                 source_reference='Course page 7', options=['A. First','B. Second'], answer='A')
    value.update(extra)
    if status == 'teacher_verified':
        value['_practice_rule'] = {'id':qid,'kind':kind,'signature':signature(value)}
    return value


def test_objective_statistics_exclude_essay_reference_counts(db_session):
    import_bank(db_session, {'questions': [sample('ready'), sample('pending', status='pending'),
                                         sample('essay', kind='essay')]})
    first, empty = chapters(db_session)[:2]
    assert first['objective_ready'] == 1 and first['objective_pending'] == 0
    assert first['kinds']['choice'] == 1 and first['kinds']['essay'] == 0
    assert empty['objective_ready'] == 0 and empty['kinds']['cell'] == 0


def test_options_are_readable_without_answer_flags(db_session):
    items = [sample('legacy', options=['A. First', 'B、Second'], answer='A'),
             sample('structured', options=[{'key': 'A', 'text': 'Option', 'correct': True}], answer='A')]
    import_bank(db_session, {'questions': items})
    rows = question_list(db_session, 1)['items']
    assert rows[0]['options'] == [{'key': 'A', 'text': 'First'}, {'key': 'B', 'text': 'Second'}]
    assert rows[1]['options'] == [{'key': 'A', 'text': 'Option'}]
    assert all('answer' not in r and 'correct' not in str(r) for r in rows)


def test_search_includes_source_but_never_reference_answers(db_session):
    import_bank(db_session, {'questions': [sample('one', answer_evidence='secret answer phrase')]})
    assert question_list(db_session, 1, search='page 7')['total'] == 1
    assert question_list(db_session, 1, search='secret answer phrase')['total'] == 0
    assert question_list(db_session, 1, search='%')['total'] == 0
