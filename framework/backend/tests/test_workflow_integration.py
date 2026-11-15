"""Member content survives restored account and examination workflows."""
import sqlite3
from contextlib import closing
import pytest

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.services.account_upgrade import upgrade_accounts
from tests.helpers import auth_headers


def test_member_database_upgrade_is_additive_backed_up_and_idempotent(tmp_path):
    database = tmp_path / 'member.db'
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT);
            INSERT INTO users VALUES (7, 'retained', 'original-hash');
            CREATE TABLE retained_answers (id INTEGER, answer TEXT);
            INSERT INTO retained_answers VALUES (1, 'original-answer');
        """)
    engine = create_engine(f'sqlite:///{database.as_posix()}')
    backup = upgrade_accounts(engine)
    try:
        assert backup and backup.is_file()
        with closing(sqlite3.connect(backup)) as connection:
            assert connection.execute('SELECT * FROM users').fetchall() == [(7, 'retained', 'original-hash')]
        with engine.connect() as connection:
            assert connection.execute(text('SELECT id,username,password_hash,is_active,token_version FROM users')).one() == (7, 'retained', 'original-hash', 1, 0)
            assert connection.execute(text('SELECT * FROM retained_answers')).one() == (1, 'original-answer')
        assert upgrade_accounts(engine) is None
    finally:
        engine.dispose()
        if backup:
            backup.unlink()


def test_fresh_database_needs_no_legacy_upgrade(tmp_path):
    engine = create_engine(f'sqlite:///{(tmp_path / "empty.db").as_posix()}')
    try:
        assert upgrade_accounts(engine) is None
        assert not inspect(engine).has_table('users')
    finally:
        engine.dispose()


def test_legacy_student_number_index_preserves_empty_values_and_blocks_duplicates(tmp_path):
    database = tmp_path / 'student-numbers.db'
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript("CREATE TABLE users (id INTEGER PRIMARY KEY, student_id TEXT); INSERT INTO users VALUES (1,''),(2,''),(3,'number-001');")
    engine = create_engine(f'sqlite:///{database.as_posix()}')
    backup = upgrade_accounts(engine)
    try:
        with engine.begin() as connection:
            assert connection.execute(text('SELECT id,student_id FROM users ORDER BY id')).all() == [(1,''),(2,''),(3,'number-001')]
            with pytest.raises(IntegrityError, match='UNIQUE'):
                connection.execute(text("INSERT INTO users(id,student_id) VALUES (4,' number-001 ' )"))
        assert upgrade_accounts(engine) is None
    finally:
        engine.dispose()
        backup.unlink()


def test_administrator_account_management_keeps_member_registration(client):
    admin = auth_headers(client, 'integration_admin', 'admin')
    created = client.post('/api/admin/users', headers=admin, json={
        'username': 'managed_student', 'password': 'managed-password', 'role': 'student',
        'real_name': '测试学生', 'student_id': 'integration-001', 'class_name': '信号一班',
    })
    assert created.status_code == 201
    uid = created.json()['id']
    assert 'password' not in created.json() and 'password_hash' not in created.json()
    login = client.post('/api/auth/login', json={'username': 'managed_student', 'password': 'managed-password'})
    token = {'Authorization': 'Bearer ' + login.json()['access_token']}
    assert client.put('/api/auth/me/contact', headers=token, json={
        'email': 'student@example.com', 'current_password': 'managed-password',
    }).status_code == 200
    assert client.post(f'/api/admin/users/{uid}/reset-password', headers=admin,
                       json={'new_password': 'replacement-password'}).status_code == 200
    assert client.get('/api/auth/me', headers=token).status_code == 401
    login = client.post('/api/auth/login', json={'username': 'managed_student', 'password': 'replacement-password'})
    assert login.status_code == 200
    assert client.delete(f'/api/admin/users/{uid}', headers=admin).status_code == 200
    assert any(row['id'] == uid and not row['is_active'] for row in client.get('/api/admin/users', headers=admin).json())
    assert client.post('/api/auth/login', json={'username': 'managed_student', 'password': 'replacement-password'}).status_code == 401
    self_registered = client.post('/api/auth/register', json={
        'username': 'self_registered', 'password': 'password123', 'role': 'student',
        'student_id': 'integration-002', 'class_name': '信号一班',
    })
    assert self_registered.status_code == 201
    duplicate = client.post('/api/auth/register', json={
        'username': 'duplicate_number', 'password': 'password123', 'role': 'student',
        'student_id': 'integration-002',
    })
    assert duplicate.status_code == 409


def test_self_password_change_revokes_previous_sessions(client):
    student = auth_headers(client, 'password_change_student', 'student')
    response = client.post('/api/auth/me/password', headers=student, json={
        'current_password': 'password123', 'new_password': 'new-password', 'confirm_password': 'new-password',
    })
    assert response.status_code == 200
    assert client.get('/api/auth/me', headers=student).status_code == 401
    assert client.post('/api/auth/login', json={'username': 'password_change_student', 'password': 'new-password'}).status_code == 200
