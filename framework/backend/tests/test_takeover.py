from tests.test_exercise_api import auth_headers, create_x_to_i_exercise
from app.api.interlocking_exam import CORRECT_ANSWERS, _load_interlocking_table_row


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


def test_four_exam_answers_and_errors(client):
    headers = auth_headers(client, 'exam_owner', 'admin')
    for route_type, answer in CORRECT_ANSWERS.items():
        payload = {k: answer[k] for k in ['route_buttons', 'switches', 'hostile_signals', 'track_sections']}
        payload['route_type'] = route_type
        result = client.post('/api/exam/submit', headers=headers, json=payload)
        assert result.status_code == 200
        assert result.json()['all_correct']
        payload['switches'] = {}
        assert not client.post('/api/exam/submit', headers=headers, json=payload).json()['all_correct']
        row = _load_interlocking_table_row(route_type)
        assert len(row.splitlines()) == 2, row


def test_ai_explanation_recomputes_errors(client, monkeypatch):
    from app.api import interlocking_exam
    headers = auth_headers(client, 'explain_owner', 'admin')
    def explain(errors, student, cache_scope=''):
        assert errors['switches']['missing']
        assert cache_scope
        return {'ai_explanation': '缺少必要道岔，不能保证进路正确。', 'source': 'rules_fallback'}
    monkeypatch.setattr(interlocking_exam, '_call_ai_for_explanation', explain)
    result = client.post('/api/exam/ai-explain', headers=headers, json={'errors': {}})
    assert result.status_code == 200
    assert '道岔' in result.json()['ai_explanation']


def test_settings_preserve_quoted_key(tmp_path, monkeypatch):
    from app.api import settings as settings_api
    env = tmp_path / '.env'
    env.write_text("DEEPSEEK_API_KEY='example-key'\nSECRET_KEY='secret'\n", encoding='utf-8')
    monkeypatch.setattr(settings_api, 'ENV_FILE', env)
    assert settings_api._read_env()['DEEPSEEK_API_KEY'] == 'example-key'
