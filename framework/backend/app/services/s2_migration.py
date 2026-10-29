"""Explicit, backed-up S2 account migration; startup checks never upgrade data."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[4]
USER_COLUMNS = {
    'email': 'VARCHAR(254)', 'phone': 'VARCHAR(32)',
    'is_active': 'BOOLEAN NOT NULL DEFAULT 1', 'token_version': 'INTEGER NOT NULL DEFAULT 0',
    'contact_failures': 'INTEGER NOT NULL DEFAULT 0', 'contact_locked': 'BOOLEAN NOT NULL DEFAULT 0',
}
INDEX = 'ux_users_student_number_s2'


def require_account_schema(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing = []
    if 'users' in tables:
        missing.extend(sorted(set(USER_COLUMNS) - {c['name'] for c in inspector.get_columns('users')}))
        unique = any(c.get('column_names') == ['student_id'] for c in
                     inspector.get_unique_constraints('users') + [i for i in inspector.get_indexes('users') if i.get('unique')])
        if not unique:
            missing.append('student_id unique index')
    if 'lab_attempts' in tables and 'identity_snapshot' not in {c['name'] for c in inspector.get_columns('lab_attempts')}:
        missing.append('identity_snapshot')
    if missing:
        raise RuntimeError('检测到S2旧结构，启动已停止且未修改数据库。请停止服务，先预览并在备份副本验证：'
                           ' .runtime/venv/Scripts/python.exe framework/backend/scripts/migrate_s2.py'
                           ' --database <项目内数据库路径>；核对后加 --apply。待迁移：' + ', '.join(missing))


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def _columns(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _digests(conn, original_columns):
    result = {}
    for name, columns in original_columns.items():
        selected = ','.join('"' + c.replace('"', '""') + '"' for c in columns)
        rows = sorted(conn.execute(f'SELECT {selected} FROM "{name}"').fetchall(), key=repr)
        raw = json.dumps(rows, ensure_ascii=False, default=repr, separators=(',', ':')).encode('utf8')
        result[name] = {'count': len(rows), 'sha256': hashlib.sha256(raw).hexdigest()}
    return result


def _preflight(conn):
    tables = _tables(conn)
    if 'users' not in tables:
        raise ValueError('数据库中没有users表；新库请通过启动初始化')
    # Report IDs only; never include credentials, contact values or student numbers in the manifest.
    duplicates = [json.loads(r[0]) for r in conn.execute(
        'SELECT json_group_array(id) FROM users WHERE student_id IS NOT NULL '
        'GROUP BY trim(student_id) HAVING count(*) > 1')]
    blank_ids = [r[0] for r in conn.execute("SELECT id FROM users WHERE student_id IS NOT NULL AND trim(student_id) = ''")]
    columns = {name: _columns(conn, name) for name in tables}
    return {'missing_user_columns': sorted(set(USER_COLUMNS) - set(columns['users'])),
            'add_identity_snapshot': 'lab_attempts' in tables and 'identity_snapshot' not in columns['lab_attempts'],
            'duplicate_student_number_user_ids': duplicates, 'blank_student_number_user_ids': blank_ids,
            'retained': _digests(conn, columns)}, columns


def migrate_database(path, *, apply=False, backup_dir=None, _fail_after_alter=False):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('数据库必须是项目内已存在的文件')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as reader:
        preview, columns = _preflight(reader)
    report = {'mode': 'apply' if apply else 'preview', 'database': str(path), **preview, 'backup': None}
    if not apply:
        return report
    if preview['duplicate_student_number_user_ids'] or preview['blank_student_number_user_ids']:
        raise ValueError('存量学号有重复或空字符串，迁移已停止且未修改；请按预览用户ID人工核对，不自动改号')
    backup_dir = Path(backup_dir or ROOT / '.runtime/backups/s2').resolve()
    if not backup_dir.is_relative_to(ROOT):
        raise ValueError('备份目录必须位于项目内')
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = backup_dir / f'{path.stem}-{stamp}-{uuid4().hex[:8]}.db'
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN IMMEDIATE')
        current, current_columns = _preflight(conn)
        if current != preview or current_columns != columns:
            raise RuntimeError('预检后数据已变化，迁移停止；请停止所有服务再试')
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        report['backup'] = str(backup)
        for name in preview['missing_user_columns']:
            conn.execute(f'ALTER TABLE users ADD COLUMN {name} {USER_COLUMNS[name]}')
        conn.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} ON users(student_id)')
        if preview['add_identity_snapshot']:
            conn.execute('ALTER TABLE lab_attempts ADD COLUMN identity_snapshot JSON')
            # This is identity at migration time, not unverifiable identity at submission time.
            conn.execute("""UPDATE lab_attempts SET identity_snapshot=(SELECT json_object(
                'id',u.id,'username',u.username,'student_name',nullif(u.real_name,''),
                'student_number',u.student_id,'class_name',nullif(u.class_name,''),'source','migration_current_identity')
                FROM users u WHERE u.id=lab_attempts.student_id)""")
        if _fail_after_alter:
            raise RuntimeError('injected failure after S2 alter')
        if _digests(conn, columns) != preview['retained']:
            raise RuntimeError('原有字段核对失败，事务回滚')
        if conn.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('存在外键悬空，事务回滚')
        conn.commit()
        report['preserved_original_fields'] = True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    manifest = backup.with_suffix('.manifest.json')
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    report['manifest'] = str(manifest)
    return report
