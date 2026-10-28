"""Catalogue filters run after visibility checks and before six-row pagination."""
from tests.helpers import auth_headers
from tests.test_s3_operations import BASE, draft, record_standard


def test_search_spans_pages_and_shares_all_course_teachers_questions(client):
    teacher = auth_headers(client, 'filter_teacher', 'teacher')
    other = auth_headers(client, 'filter_other', 'teacher')
    for index in range(8):
        draft(client, teacher, title=f'调车练习 {index}', classes=['一班' if index % 2 else '二班'])
    draft(client, other, title='调车练习 隐私', classes=['一班'])
    first = client.get(BASE + '/questions', headers=teacher, params={'search': '调车练习'}).json()
    second = client.get(BASE + '/questions', headers=teacher, params={'search': '调车练习', 'page': 2}).json()
    assert first['total'] == second['total'] == 9
    assert len(first['items']) == 6 and len(second['items']) == 3
    assert not ({q['id'] for q in first['items']} & {q['id'] for q in second['items']})
    by_class = client.get(BASE + '/questions', headers=teacher, params={'search': ' 一班 '}).json()
    assert by_class['total'] == 5
    assert all(q['classes'] == ['一班'] for q in by_class['items'])
    assert client.get(BASE + '/questions', headers=teacher, params={'search': '隐私'}).json()['total'] == 1


def test_filters_preserve_student_class_and_published_visibility(client):
    teacher = auth_headers(client, 'visible_teacher', 'teacher')
    student = auth_headers(client, 'visible_student', 'student')
    admin = auth_headers(client, 'visible_admin', 'admin')
    published = draft(client, teacher, title='公开题面')
    record_standard(client, teacher, published['id'])
    assert client.post(f"{BASE}/questions/{published['id']}/publish", headers=teacher).status_code == 200
    hidden_class = draft(client, teacher, title='别班题面', classes=['信号二班'])
    record_standard(client, teacher, hidden_class['id'])
    assert client.post(f"{BASE}/questions/{hidden_class['id']}/publish", headers=teacher).status_code == 200
    draft(client, teacher, title='草稿题面')
    disabled = draft(client, teacher, title='停用题面')
    assert client.post(f"{BASE}/questions/{disabled['id']}/disable", headers=teacher).status_code == 200
    for status, total in [('all', 4), ('draft', 1), ('published', 2), ('disabled', 1)]:
        assert client.get(BASE + '/questions', headers=admin, params={'status': status}).json()['total'] == total
    for term in ['', '公开']:
        data = client.get(BASE + '/questions', headers=student, params={'search': term, 'status': 'published'}).json()
        assert data['total'] == 1 and data['items'][0]['id'] == published['id']
        assert 'standard_log' not in data['items'][0] and 'standard_session_id' not in data['items'][0]
    for term in ['别班', '草稿', '停用']:
        assert client.get(BASE + '/questions', headers=student, params={'search': term}).json()['total'] == 0
    for status in ['draft', 'disabled']:
        assert client.get(BASE + '/questions', headers=student, params={'status': status}).json()['total'] == 0


def test_invalid_filters_are_rejected_without_falling_back_to_unfiltered_data(client):
    teacher = auth_headers(client, 'invalid_filter_teacher', 'teacher')
    for params in [{'search': 'a' * 201}, {'status': 'private'}, {'page': 0}]:
        assert client.get(BASE + '/questions', headers=teacher, params=params).status_code == 422
