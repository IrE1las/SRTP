import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import settings as api
from app.schemas.settings import AISettingsUpdate


def test_save_preserves_secret_and_quoted_values(tmp_path, monkeypatch):
    env = tmp_path / 'server.env'
    env.write_text('# server configuration\nSECRET_KEY=preserve-me\n', encoding='utf8')
    monkeypatch.setattr(api, 'ENV_FILE', env)
    changes = {}
    monkeypatch.setattr(api, '_update_runtime_config', lambda *args: changes.update(values=args))
    value = "example key with 'quotes' # and spaces"
    result = api.update_ai_settings(AISettingsUpdate(api_key=value, model='deepseek-flash',
                                                    base_url='https://api.deepseek.com'), None)
    assert result['success']
    assert api._read_env()['DEEPSEEK_API_KEY'] == value
    assert api._read_env()['SECRET_KEY'] == 'preserve-me'
    assert '# server configuration' in env.read_text(encoding='utf8')
    assert changes['values'][0] == value


def test_omitted_key_retains_injected_runtime_key(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'ENV_FILE', tmp_path / '.env')
    monkeypatch.setattr(api.settings, 'deepseek_api_key', 'injected-example-key')
    monkeypatch.setattr(api, '_update_runtime_config', lambda *args: None)
    api.update_ai_settings(AISettingsUpdate(model='deepseek-flash', base_url='https://api.deepseek.com'), None)
    assert api._read_env()['DEEPSEEK_API_KEY'] == 'injected-example-key'


def test_write_failure_reports_actionable_error_without_runtime_change(tmp_path, monkeypatch):
    env = tmp_path / '.env'
    env.write_text('SECRET_KEY=preserve-me\n', encoding='utf8')
    monkeypatch.setattr(api, 'ENV_FILE', env)
    def fail(_):
        raise PermissionError('private filesystem details')
    monkeypatch.setattr(api, '_write_env', fail)
    monkeypatch.setattr(api, '_update_runtime_config', lambda *args: pytest.fail('runtime changed after failure'))
    with pytest.raises(HTTPException) as failure:
        api.update_ai_settings(AISettingsUpdate(api_key='example-key', model='deepseek-flash',
                                               base_url='https://api.deepseek.com'), None)
    assert failure.value.status_code == 503
    assert '不可写' in failure.value.detail
    assert 'private filesystem' not in failure.value.detail
    assert env.read_text(encoding='utf8') == 'SECRET_KEY=preserve-me\n'


def test_restart_reads_saved_ai_values_over_container_environment(tmp_path):
    env = tmp_path / 'server.env'
    env.write_text("SECRET_KEY=test-only-secret\nDEEPSEEK_API_KEY='saved-example-key'\n"
                   "DEEPSEEK_MODEL='deepseek-flash'\nDEEPSEEK_BASE_URL='https://api.deepseek.com'\n",
                   encoding='utf8')
    process_env = dict(os.environ, SRTP_ENV_FILE=str(env), DEEPSEEK_API_KEY='',
                       DEEPSEEK_MODEL='stale-container-model', DEEPSEEK_BASE_URL='https://stale.invalid')
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c',
        "from app.core.config import settings; "
        "assert settings.deepseek_api_key == 'saved-example-key'; "
        "assert settings.deepseek_model == 'deepseek-flash'; "
        "assert settings.deepseek_base_url == 'https://api.deepseek.com'"],
        env=process_env, cwd=backend, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
