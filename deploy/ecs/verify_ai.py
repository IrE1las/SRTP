"""Verify deployed AI settings without printing credentials or tokens."""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8000/api'


def request(path, body=None, token=None, method=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as failure:
        raise SystemExit(f'{path}: HTTP {failure.code}; no credentials logged') from None


token = request('/auth/login', {'username': 'admin', 'password': os.environ['SRTP_ADMIN_PASSWORD']})['access_token']
if '--save' in sys.argv:
    result = request('/settings/ai', {'api_key': os.environ['SRTP_AI_KEY'], 'model': 'deepseek-flash',
                                     'base_url': 'https://api.deepseek.com'}, token, 'PUT')
    assert result['success']
    print('Save AI settings via authenticated HTTP API: OK')
current = request('/settings/ai', token=token)
assert current['model'] == 'deepseek-flash'
assert current['base_url'] == 'https://api.deepseek.com'
assert current['api_key_masked'] and '*' in current['api_key_masked']
print('Read masked settings: OK; model=deepseek-flash; base_url=https://api.deepseek.com')
if '--test' in sys.argv:
    result = request('/settings/ai/test', {'model': current['model'], 'base_url': current['base_url']}, token)
    print('Provider connection test:', json.dumps(result, ensure_ascii=False))
    assert result['success'], 'Provider connection test failed'
