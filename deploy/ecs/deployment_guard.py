"""Back up and compare server data without logging accounts or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def inspect_data(database, config):
    with readonly(database) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        counts = {name: db.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                  for name in tables}
        columns = [r[1] for r in db.execute('PRAGMA table_info(users)')]
        users = db.execute('SELECT * FROM users ORDER BY id').fetchall()
        assert users, 'Refusing to deploy over an empty account database'
        account_hash = hashlib.sha256(json.dumps([columns, users], default=str).encode()).hexdigest()
    return {'accounts': len(users), 'accounts_digest': account_hash, 'table_counts': counts,
            'config_digest': hashlib.sha256(config.read_bytes()).hexdigest()}


def capture(runtime, directory):
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    with readonly(runtime / 'railway.db') as source, sqlite3.connect(directory / 'railway.db') as target:
        source.backup(target)
    shutil.copy2(runtime / 'server.env', directory / 'server.env')
    baseline = inspect_data(directory / 'railway.db', directory / 'server.env')
    (directory / 'baseline.json').write_text(json.dumps(baseline, indent=2), encoding='utf8')
    print(json.dumps({'backup': str(directory), 'accounts': baseline['accounts'], 'integrity': 'ok'}))


def verify(runtime, directory):
    before = json.loads((directory / 'baseline.json').read_text(encoding='utf8'))
    after = inspect_data(runtime / 'railway.db', runtime / 'server.env')
    assert before['accounts_digest'] == after['accounts_digest'], 'Account data changed; do not switch traffic'
    assert before['config_digest'] == after['config_digest'], 'Server settings changed; do not switch traffic'
    for name, count in before['table_counts'].items():
        assert name in after['table_counts'], f'Existing table removed: {name}'
        assert after['table_counts'][name] >= count, f'Existing table lost records: {name}'
    result = {'accounts_unchanged': True, 'server_settings_unchanged': True, 'existing_records_retained': True,
              'accounts': after['accounts'], 'lab_questions': after['table_counts'].get('lab_questions')}
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['capture', 'verify'])
    parser.add_argument('--runtime', type=Path, default=Path('/app/.runtime'))
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    (capture if args.action == 'capture' else verify)(args.runtime, args.directory)
