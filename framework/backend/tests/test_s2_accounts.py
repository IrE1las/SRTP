"""R02 account lifecycle and privacy using synthetic accounts in an isolated database."""
import bcrypt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import LabAttempt, LabQuestion, User
from app.services.bootstrap import seed_theory
from tests.helpers import auth_headers
from tests.test_lab_topics import completed


@pytest.fixture()
def accounts(client, db_session):
    admin = auth_headers(client, 's2_admin', 'admin')
    student = auth_headers(client, 's2_student', 'student')
    teacher = auth_headers(client, 's2_teacher', 'teacher')
    people = {u.role: u.id for u in db_session.query(User).all()}
    return {**people, 'admin_auth': admin, 'student_auth': student, 'teacher_auth': teacher}


def login(client, username, password):
    return client.post('/api/auth/login', json={'username': username, 'password': password})


def headers(response):
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


@pytest.mark.parametrize('role', ['student', 'teacher'])
@pytest.mark.parametrize('method,path,body', [
    ('post', '/api/admin/users', {'username': 'intruder', 'password': 'x', 'role': 'teacher'}),
    ('put', '/api/admin/users/{id}', {'role': 'admin', 'student_id': 'hacked'}),
    ('put', '/api/admin/users/{id}', {'is_active': False}),
    ('post', '/api/admin/users/{id}/reset-password', {'new_password': 'x'}),
    ('delete', '/api/admin/users/{id}', None),
    ('get', '/api/admin/users', None),
])
def test_non_admin_cannot_manage_accounts(client, accounts, role, method, path, body):
    response = client.request(method, path.format(id=accounts['student']),
                              headers=accounts[role + '_auth'], json=body)
    assert response.status_code == 403


@pytest.mark.parametrize('body', [{}, {'role': 'admin'}, {'username': 's2_public', 'password': 'x', 'role': 'teacher'}])
def test_registration_always_closed(client, db_session, body):
    before = db_session.query(User).count()
    assert client.post('/api/auth/register', json=body).status_code == 403
    assert db_session.query(User).count() == before


def test_admin_builds_students_two_classes_and_teacher_and_uniqueness(client, accounts, db_session):
    admin = accounts['admin_auth']
    for n in (1, 2):
        data = {'username': f's2_new{n}', 'password': '一', 'role': 'student', 'real_name': f'测试学生{n}',
                'student_id': f'TEST-{n}', 'class_name': f'测试{n}班'}
        created = client.post('/api/admin/users', headers=admin, json=data)
        assert created.status_code == 201, created.text
        assert created.json()['email'] is created.json()['phone'] is None
        assert 'password' not in created.text and 'token_version' not in created.text
        assert login(client, data['username'], '一').status_code == 200
        assert client.post('/api/admin/users', headers=admin, json={**data, 'username': f'duplicate{n}'}).status_code == 409
        assert client.post('/api/admin/users', headers=admin, json={**data, 'student_id': f'OTHER-{n}'}).status_code == 409
    assert client.post('/api/admin/users', headers=admin,
                       json={'username': 's2_newteacher', 'password': 'x', 'role': 'teacher'}).status_code == 201
    for body in [dict(username='missing', password='x'), dict(username='blank', password='x', real_name='  ', student_id='x', class_name='c'),
                 dict(username='admin2', password='x', role='admin'), dict(username='badrole', password='x', role='unknown')]:
        assert client.post('/api/admin/users', headers=admin, json=body).status_code == 422
    changed = client.put(f"/api/admin/users/{accounts['student']}", headers=admin, json={'student_id': 'TEST-1', 'class_name': '不应保存'})
    assert changed.status_code == 409
    assert db_session.get(User, accounts['student']).class_name == '信号一班'


@pytest.mark.parametrize('role', ['student', 'teacher', 'admin'])
def test_contacts_require_current_password_and_remain_after_reopening_session(client, accounts, db_session, role):
    auth = accounts[role + '_auth']
    assert client.get('/api/auth/me', headers=auth).json()['email'] is None
    payload = {'current_password': 'wrong', 'email': 'sample@example.com', 'phone': '13800138000'}
    assert client.put('/api/auth/me/contact', headers=auth, json=payload).status_code == 400
    assert client.get('/api/auth/me', headers=auth).json()['email'] is None
    payload['current_password'] = 'password123'
    saved = client.put('/api/auth/me/contact', headers=auth, json=payload)
    assert saved.status_code == 200 and saved.json()['email'] == payload['email']
    assert 'password123' not in saved.text and 'password_hash' not in saved.text
    with Session(db_session.bind) as second:
        assert second.get(User, accounts[role]).phone == payload['phone']
    # Omitted contact fields are retained; explicit null alone clears a field.
    assert client.put('/api/auth/me/contact', headers=auth,
                      json={'current_password': 'password123'}).status_code == 200
    partial = client.put('/api/auth/me/contact', headers=auth,
                         json={'current_password': 'password123', 'phone': '13900139000'})
    assert partial.json()['email'] == payload['email']
    for invalid in [{'email': 'bad'}, {'phone': 'abc'}, {'role': 'admin'}, {'real_name': '篡改'},
                    {'student_id': '篡改'}, {'class_name': '篡改'}, {'is_active': False}]:
        response = client.put('/api/auth/me/contact', headers=auth, json={**payload, **invalid})
        assert response.status_code == 422
        assert 'password123' not in response.text
        assert client.get('/api/auth/me', headers=auth).json()['email'] == payload['email']
    cleared = client.put('/api/auth/me/contact', headers=auth,
                         json={'current_password': 'password123', 'email': ' ', 'phone': None})
    assert cleared.status_code == 200
    assert cleared.json()['email'] is cleared.json()['phone'] is None


@pytest.mark.parametrize('role', ['student', 'teacher', 'admin'])
def test_password_change_revokes_every_token_and_preserves_failed_changes(client, accounts, role):
    username = 's2_' + role
    auth = accounts[role + '_auth']
    other = headers(login(client, username, 'password123'))
    for body, code in [({'current_password': 'wrong', 'new_password': 'x', 'confirm_password': 'x'}, 400),
                       ({'current_password': 'password123', 'new_password': 'x', 'confirm_password': 'y'}, 400),
                       ({'current_password': 'password123', 'new_password': '', 'confirm_password': ''}, 422)]:
        response = client.post('/api/auth/me/password', headers=auth, json=body)
        assert response.status_code == code
        assert 'password123' not in response.text
        assert client.get('/api/auth/me', headers=auth).status_code == 200
    changed = client.post('/api/auth/me/password', headers=auth,
                          json={'current_password': 'password123', 'new_password': '新', 'confirm_password': '新'})
    assert changed.status_code == 200
    assert client.get('/api/auth/me', headers=auth).status_code == 401
    assert client.get('/api/auth/me', headers=other).status_code == 401
    assert login(client, username, 'password123').status_code == 401
    assert login(client, username, '新').status_code == 200


def test_reset_disable_reenable_and_self_protection(client, accounts, db_session):
    admin, student = accounts['admin_auth'], accounts['student_auth']
    path = f"/api/admin/users/{accounts['student']}"
    assert client.post(path + '/reset-password', headers=admin, json={'new_password': 'reset'}).status_code == 200
    assert client.get('/api/auth/me', headers=student).status_code == 401
    assert login(client, 's2_student', 'password123').status_code == 401
    fresh = headers(login(client, 's2_student', 'reset'))
    assert client.put(path, headers=admin, json={'is_active': False}).status_code == 200
    assert client.get('/api/auth/me', headers=fresh).status_code == 401
    assert client.get('/api/lab-topics/questions', headers=fresh).status_code == 401
    assert login(client, 's2_student', 'reset').status_code == 401
    assert client.put(path, headers=admin, json={'is_active': True}).status_code == 200
    assert client.get('/api/auth/me', headers=fresh).status_code == 401
    assert login(client, 's2_student', 'reset').status_code == 200
    own = f"/api/admin/users/{accounts['admin']}"
    for body in [{'role': 'teacher'}, {'is_active': False}]:
        assert client.put(own, headers=admin, json=body).status_code == 400
    assert client.delete(own, headers=admin).status_code == 400
    assert client.post(own + '/reset-password', headers=admin, json={'new_password': 'x'}).status_code == 400
    for body in [{'role': None}, {'is_active': None}, {'role': 'unknown'}, {'password_hash': 'hack'}, {'token_version': 0}]:
        assert client.put(path, headers=admin, json=body).status_code == 422
    assert client.get('/api/auth/me', headers=admin).status_code == 200
    assert client.put('/api/admin/users/99999', headers=admin, json={'class_name': 'c'}).status_code == 404


def test_history_identity_survives_edit_role_change_and_deactivation(client, accounts, db_session):
    seed_theory(db_session)
    q = db_session.query(LabQuestion).first()
    submitted = client.post(f'/api/lab-topics/questions/{q.key}/submit', headers=accounts['student_auth'],
                            json={'fingerprint': q.fingerprint, 'answers': completed(q)})
    assert submitted.status_code == 201
    attempt_id = submitted.json()['id']
    original = submitted.json()['identity_snapshot']
    path = f"/api/admin/users/{accounts['student']}"
    assert client.put(path, headers=accounts['admin_auth'], json={'real_name': '新姓名', 'student_id': 'NEW-ID', 'class_name': '新班级'}).status_code == 200
    assert client.put(path, headers=accounts['admin_auth'], json={'role': 'teacher'}).status_code == 200
    assert client.delete(path, headers=accounts['admin_auth']).status_code == 200
    assert db_session.query(LabAttempt).filter_by(id=attempt_id).one().identity_snapshot == original
    detail = client.get(f'/api/lab-topics/review-attempts/{attempt_id}', headers=accounts['teacher_auth']).json()
    assert detail['student'] == original
    roster = client.get('/api/lab-topics/review-students', headers=accounts['teacher_auth']).json()
    assert any(row['id'] == accounts['student'] for row in roster)
    assert client.get(f"/api/lab-topics/review-students/{accounts['student']}/attempts", headers=accounts['teacher_auth']).status_code == 200


def test_old_missing_identity_can_be_filled_without_fabrication(client, accounts, db_session):
    old = User(username='legacy_missing', password_hash=get_password_hash('x'), role='student', real_name='', class_name='')
    db_session.add(old)
    db_session.commit()
    auth = headers(login(client, old.username, 'x'))
    profile = client.get('/api/auth/me', headers=auth).json()
    assert all(profile[k] is None for k in ('real_name', 'student_id', 'class_name', 'email', 'phone'))
    assert client.put(f'/api/admin/users/{old.id}', headers=accounts['admin_auth'], json={'class_name': '补录班级'}).status_code == 200
    assert client.get('/api/auth/me', headers=auth).json()['real_name'] is None


def test_long_passwords_not_truncated_legacy_hash_still_works_and_old_tokens_rejected(client, accounts):
    secret = '汉' * 40 + '甲'
    hashed = get_password_hash(secret)
    assert verify_password(secret, hashed)
    assert not verify_password('汉' * 40 + '乙', hashed)
    legacy = bcrypt.hashpw(b'legacy', bcrypt.gensalt()).decode()
    assert verify_password('legacy', legacy)
    assert not verify_password('wrong', legacy)
    token = create_access_token({'sub': str(accounts['student']), 'role': 'student'})
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


@pytest.mark.parametrize('endpoint,payload', [
    ('/api/auth/login', {'username': 'x', 'password': {'secret': 'NEVER-ECHO-THIS'}}),
    ('/api/auth/me/password', {'current_password': 'NEVER-ECHO-THIS', 'new_password': [], 'confirm_password': 'x'}),
    ('/api/admin/users', {'username': 'x', 'password': 'NEVER-ECHO-THIS', 'role': 'bad'}),
])
def test_validation_does_not_echo_credentials(client, accounts, endpoint, payload, caplog):
    response = client.post(endpoint, headers=accounts['admin_auth'], json=payload)
    assert response.status_code == 422
    assert 'NEVER-ECHO-THIS' not in response.text
    assert 'NEVER-ECHO-THIS' not in caplog.text
    assert all('input' not in error for error in response.json()['detail'])
