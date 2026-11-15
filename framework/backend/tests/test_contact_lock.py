"""Contact verification uses durable account state, independent of login or password reset."""
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.user import ContactUpdate
from app.services.contact_service import update_contacts
from tests.helpers import auth_headers


@pytest.fixture()
def people(client, db_session):
    headers = {role: auth_headers(client, 'lock_' + role, role) for role in ('admin', 'student', 'teacher')}
    ids = {u.role: u.id for u in db_session.query(User).all()}
    return headers, ids


def save(client, auth, password='wrong', **values):
    return client.put('/api/auth/me/contact', headers=auth, json={
        'current_password': password, 'email': 'locked@example.invalid', 'phone': '13800138000', **values,
    })


@pytest.mark.parametrize('role', ['student', 'teacher'])
def test_fifth_failure_locks_persistently_and_only_admin_unlocks(client, db_session, people, role):
    auth, ids = people
    for count in range(1, 6):
        result = save(client, auth[role])
        assert result.status_code == (403 if count == 5 else 400)
        profile = client.get('/api/auth/me', headers=auth[role]).json()
        assert profile['contact_failures'] == count
        assert profile['contact_locked'] is (count == 5)
        assert profile['email'] is profile['phone'] is None
    assert save(client, auth[role], 'password123').status_code == 403
    # New login and a new DB session still observe the lock.
    login = client.post('/api/auth/login', json={'username': 'lock_' + role, 'password': 'password123'})
    fresh = {'Authorization': 'Bearer ' + login.json()['access_token']}
    assert login.json()['user']['contact_locked']
    with Session(db_session.bind) as second:
        assert second.get(User, ids[role]).contact_locked
    assert save(client, fresh, 'password123').status_code == 403
    for denied in ('student', 'teacher'):
        assert client.post(f"/api/admin/users/{ids[role]}/unlock-contact", headers=auth[denied]).status_code == 403
    assert client.put('/api/auth/me/contact', headers=fresh, json={
        'current_password': 'password123', 'contact_locked': False, 'contact_failures': 0,
    }).status_code == 422
    unlocked = client.post(f"/api/admin/users/{ids[role]}/unlock-contact", headers=auth['admin'])
    assert unlocked.status_code == 200
    assert not unlocked.json()['contact_locked'] and unlocked.json()['contact_failures'] == 0
    saved = save(client, fresh, 'password123')
    assert saved.status_code == 200 and saved.json()['email'] == 'locked@example.invalid'


@pytest.mark.parametrize('role', ['student', 'teacher'])
def test_success_resets_consecutive_failures_and_invalid_format_is_not_password_failure(client, people, role):
    auth, _ = people
    for _ in range(4):
        assert save(client, auth[role]).status_code == 400
    assert save(client, auth[role], 'password123', email='bad-format').status_code == 422
    assert client.get('/api/auth/me', headers=auth[role]).json()['contact_failures'] == 4
    assert save(client, auth[role], 'password123').json()['contact_failures'] == 0
    assert save(client, auth[role]).status_code == 400
    assert client.get('/api/auth/me', headers=auth[role]).json()['contact_failures'] == 1


def test_admin_not_subject_to_contact_lock_and_unlock_cannot_change_account_status(client, people):
    auth, ids = people
    for _ in range(6):
        assert save(client, auth['admin']).status_code == 400
    profile = client.get('/api/auth/me', headers=auth['admin']).json()
    assert not profile['contact_locked'] and profile['contact_failures'] == 0
    assert client.post(f"/api/admin/users/{ids['admin']}/unlock-contact", headers=auth['admin']).status_code == 400
    for _ in range(5):
        save(client, auth['student'])
    client.put(f"/api/admin/users/{ids['student']}", headers=auth['admin'], json={'is_active': False})
    unlocked = client.post(f"/api/admin/users/{ids['student']}/unlock-contact", headers=auth['admin']).json()
    assert not unlocked['is_active'] and not unlocked['contact_locked']
    assert client.post('/api/admin/users/999999/unlock-contact', headers=auth['admin']).status_code == 404


def test_password_change_and_admin_reset_do_not_unlock_contacts(client, people):
    auth, ids = people
    for _ in range(5):
        save(client, auth['student'])
    result = client.post('/api/auth/me/password', headers=auth['student'], json={
        'current_password': 'password123', 'new_password': 'new', 'confirm_password': 'new',
    })
    assert result.status_code == 200
    login = client.post('/api/auth/login', json={'username': 'lock_student', 'password': 'new'})
    fresh = {'Authorization': 'Bearer ' + login.json()['access_token']}
    assert login.json()['user']['contact_locked']
    assert save(client, fresh, 'new').status_code == 403
    client.post(f"/api/admin/users/{ids['student']}/reset-password", headers=auth['admin'], json={'new_password': 'reset'})
    login = client.post('/api/auth/login', json={'username': 'lock_student', 'password': 'reset'})
    assert login.json()['user']['contact_locked'] and login.json()['user']['contact_failures'] == 5


def test_concurrent_failures_use_atomic_count_and_never_exceed_five(db_session):
    from app.core.security import get_password_hash
    person = User(username='concurrent_lock', password_hash=get_password_hash('correct'), role='student')
    db_session.add(person)
    db_session.commit()
    person_id = person.id

    def wrong_request(_):
        with Session(db_session.bind) as db:
            user = db.get(User, person_id)
            try:
                update_contacts(db, user, ContactUpdate(current_password='wrong', email='not-saved@example.invalid'))
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(wrong_request, range(8)))
    assert all(status in (400, 403) for status in statuses)
    with Session(db_session.bind) as db:
        user = db.get(User, person_id)
        assert user.contact_failures == 5 and user.contact_locked
        assert user.email is None
        with pytest.raises(HTTPException) as denied:
            update_contacts(db, user, ContactUpdate(current_password='correct', email='still-not-saved@example.invalid'))
        assert denied.value.status_code == 403
