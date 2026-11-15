from tests.test_exercise_api import auth_headers, create_x_to_i_exercise


def test_admin_handover_permissions(client):
    denied = client.post('/api/auth/register', json={'username': 'intruder', 'password': 'password123', 'role': 'admin'})
    assert denied.status_code == 403
    admin = auth_headers(client, 'owner', 'admin')
    teacher = auth_headers(client, 'teacher_owner', 'teacher')
    exercise = create_x_to_i_exercise(client, teacher)
    assert any(row['id'] == exercise for row in client.get('/api/exercises/teacher', headers=admin).json())
    me = client.get('/api/auth/me', headers=admin).json()
    assert client.delete(f"/api/admin/users/{me['id']}", headers=admin).status_code == 400
    assert client.put(f"/api/admin/users/{me['id']}", headers=admin, json={'role': 'student'}).status_code == 400






def test_settings_preserve_quoted_key(tmp_path, monkeypatch):
    from app.api import settings as settings_api
    env = tmp_path / '.env'
    env.write_text("DEEPSEEK_API_KEY='example-key'\nSECRET_KEY='secret'\n", encoding='utf-8')
    monkeypatch.setattr(settings_api, 'ENV_FILE', env)
    assert settings_api._read_env()['DEEPSEEK_API_KEY'] == 'example-key'
