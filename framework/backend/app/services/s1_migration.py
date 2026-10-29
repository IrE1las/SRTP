"""Explicit, backed-up SQLite migration for S1; startup only checks, never deletes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[4]
CANONICAL = {f'lab-{topic:02d}-{sequence:02d}': topic
             for topic in range(1, 7) for sequence in range(1, 4)}
# Children before parents. These tables belong exclusively to removed features.
REMOVED_TABLES = ('module_one_events', 'module_one_attempts', 'ai_scores',
                  'operation_logs', 'exercise_sessions', 'exercises', 'shunting_questions',
                  'device_states', 'route_states', 'interlocking_tables', 'switches',
                  'signals', 'sections', 'stations')


def require_current_schema(engine):
    tables = set(inspect(engine).get_table_names())
    reason = sorted(tables.intersection(REMOVED_TABLES))
    if 'lab_questions' in tables:
        with engine.connect() as conn:
            rows = conn.execute(text('SELECT key, topic FROM lab_questions')).all()
            if any(CANONICAL.get(key) != topic for key, topic in rows):
                reason.append('six-topic data migration required')
    if reason:
        raise RuntimeError('检测到旧功能数据，启动已停止且未修改数据库。请停止服务，先预览并备份迁移：'
                           ' .runtime/venv/Scripts/python.exe framework/backend/scripts/migrate_s1.py'
                           ' --database <项目内数据库路径>；核对后加 --apply。待迁移：' + ', '.join(reason))


def _tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _retained_ids(conn, tables):
    if 'lab_questions' not in tables:
        return []
    return [row[0] for row in conn.execute('SELECT id,key,topic FROM lab_questions')
            if CANONICAL.get(row[1]) == row[2]]


def _protected(conn, tables, ids):
    """Digest exact retained row values, including identity, answers and historical rubrics."""
    result = {}
    for name in ('users', 'shunting_datasets', 'shunting_routes', 'lab_questions', 'lab_attempts',
                 'question_workspaces', 'question_revisions', 'grade_drafts', 'grade_audits', 'feedback_snippets'):
        if name not in tables:
            continue
        sql = f'SELECT * FROM "{name}"'
        args = ()
        if name == 'lab_questions':
            sql += ' WHERE id IN (SELECT value FROM json_each(?))'
            args = (json.dumps(ids),)
        elif name in ('lab_attempts', 'question_workspaces', 'question_revisions'):
            sql += ' WHERE question_id IN (SELECT value FROM json_each(?))'
            args = (json.dumps(ids),)
        elif name in ('grade_drafts', 'grade_audits'):
            sql += ' WHERE attempt_id IN (SELECT id FROM lab_attempts WHERE question_id IN (SELECT value FROM json_each(?)))'
            args = (json.dumps(ids),)
        rows = sorted([tuple(row) for row in conn.execute(sql, args)], key=repr)
        raw = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf8')
        result[name] = {'count': len(rows), 'sha256': hashlib.sha256(raw).hexdigest()}
    return result


def _delete_unretained(conn, table, column, values):
    if table in _tables(conn):
        conn.execute(f'DELETE FROM "{table}" WHERE "{column}" NOT IN (SELECT value FROM json_each(?))',
                     (json.dumps(values),))


def migrate_database(path, *, apply=False, backup_dir=None, _fail_after_cleanup=False):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('数据库必须是项目内已存在的文件，不创建或迁移项目外数据库')
    # Read-only preflight never creates a DB, journal, secret copy or backup.
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as reader:
        tables = _tables(reader)
        ids = _retained_ids(reader, tables)
        protected = _protected(reader, tables, ids)
        counts = {t:reader.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
                  for t in REMOVED_TABLES if t in tables}
        all_questions = reader.execute('SELECT count(*) FROM lab_questions').fetchone()[0] if 'lab_questions' in tables else 0
        all_attempts = reader.execute('SELECT count(*) FROM lab_attempts').fetchone()[0] if 'lab_attempts' in tables else 0
    report = {'mode':'apply' if apply else 'preview', 'database':str(path), 'removed_tables':counts,
              'remove_questions':all_questions - len(ids),
              'remove_attempts':all_attempts - protected.get('lab_attempts', {}).get('count', 0),
              'retained':protected, 'backup':None}
    if not apply:
        return report
    # The application must be stopped. A write reservation makes backup+cleanup one consistent snapshot.
    backup_dir = Path(backup_dir or ROOT / '.runtime/backups/s1').resolve()
    if not backup_dir.is_relative_to(ROOT):
        raise ValueError('备份目录必须位于项目内')
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = backup_dir / f'{path.stem}-{stamp}-{uuid4().hex[:8]}.db'
    conn = sqlite3.connect(path, timeout=5)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN IMMEDIATE')
        # Dedicated read connection backs up the same committed state while writers are excluded.
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        report['backup'] = str(backup)
        tables = _tables(conn)
        ids = _retained_ids(conn, tables)
        protected = _protected(conn, tables, ids)
        if protected != report['retained']:
            raise RuntimeError('预检后数据已变化；未执行迁移，请停止所有服务再试')
        attempt_ids = [row[0] for row in conn.execute(
            'SELECT id FROM lab_attempts WHERE question_id IN (SELECT value FROM json_each(?))', (json.dumps(ids),)
        )] if 'lab_attempts' in tables else []
        for table in ('grade_audits', 'grade_drafts'):
            _delete_unretained(conn, table, 'attempt_id', attempt_ids)
        for table in ('lab_attempts', 'question_revisions', 'question_workspaces'):
            _delete_unretained(conn, table, 'question_id', ids)
        _delete_unretained(conn, 'lab_questions', 'id', ids)
        for name in REMOVED_TABLES:
            if name in tables:
                conn.execute(f'DROP TABLE "{name}"')
        if _fail_after_cleanup:
            raise RuntimeError('injected failure after cleanup')
        if _protected(conn, _tables(conn), ids) != protected:
            raise RuntimeError('保留数据核对失败，事务已回滚')
        if conn.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('迁移后有外键悬空，事务已回滚')
        conn.commit()
        report['preserved_exactly'] = True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    manifest = backup.with_suffix('.manifest.json')
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    report['manifest'] = str(manifest)
    return report
