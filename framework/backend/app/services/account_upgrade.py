"""Add account fields to member databases without replacing teaching records."""
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy import inspect, text

FIELDS = {
    'email': 'VARCHAR(254)', 'phone': 'VARCHAR(32)',
    'contact_failures': 'INTEGER NOT NULL DEFAULT 0',
    'contact_locked': 'BOOLEAN NOT NULL DEFAULT 0',
    'is_active': 'BOOLEAN NOT NULL DEFAULT 1',
    'token_version': 'INTEGER NOT NULL DEFAULT 0',
}


def upgrade_accounts(engine):
    """Idempotent SQLite extension; keep a recovery copy before changing a file."""
    inspector = inspect(engine)
    if not inspector.has_table('users'):
        return None
    existing = {c['name'] for c in inspector.get_columns('users')}
    missing = {name: ddl for name, ddl in FIELDS.items() if name not in existing}
    with engine.connect() as connection:
        has_index = engine.dialect.name == 'sqlite' and connection.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='uq_account_student_number'"
        )).first() is not None
    unique_student_id = has_index or any(c['column_names'] == ['student_id'] for c in inspector.get_unique_constraints('users'))
    add_index = 'student_id' in existing and not unique_student_id and not has_index
    if not missing and not add_index:
        return None
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('账号字段需要显式迁移；当前自动升级仅支持 SQLite。')
    if add_index:
        with engine.connect() as connection:
            duplicates = connection.execute(text(
                "SELECT 1 FROM users WHERE student_id IS NOT NULL AND trim(student_id) != '' "
                "GROUP BY trim(student_id) HAVING count(*) > 1 LIMIT 1"
            )).first()
        if duplicates:
            raise RuntimeError('检测到重复学号，未更改数据库。请先核对并修正重复账号的学号后重试。')
    backup = None
    database = engine.url.database
    if database and database != ':memory:':
        project = Path(__file__).resolve().parents[4]
        directory = project / '.runtime' / 'account-upgrade-backups'
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = directory / f'accounts-before-{stamp}-{uuid4().hex[:8]}.db'
        with closing(sqlite3.connect(f'{Path(database).resolve().as_uri()}?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(backup)) as target:
                source.backup(target)
    with engine.begin() as connection:
        for name, ddl in missing.items():
            connection.execute(text(f'ALTER TABLE users ADD COLUMN {name} {ddl}'))
        if add_index:
            connection.execute(text(
                "CREATE UNIQUE INDEX uq_account_student_number ON users (trim(student_id)) "
                "WHERE student_id IS NOT NULL AND trim(student_id) != ''"
            ))
    return backup
