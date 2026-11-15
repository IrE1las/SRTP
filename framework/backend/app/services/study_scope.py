"""Retire explicitly removed study content, with a local recovery copy first."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4
from sqlalchemy import inspect, text

REMOVED_TABLES = ('module_one_events', 'module_one_attempts', 'learning_archive_events', 'learning_archives')


def retire_study_scope(engine):
    tables = set(inspect(engine).get_table_names())
    retired_tables = [name for name in REMOVED_TABLES if name in tables]
    with engine.connect() as db:
        retired_questions = db.execute(text('SELECT count(*) FROM lab_questions WHERE topic IN (7,8)')).scalar() if 'lab_questions' in tables else 0
    if not retired_tables and not retired_questions:
        return None
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('本次内容清理仅支持已备份的 SQLite 数据库。')
    backup = None
    if engine.url.database and engine.url.database != ':memory:':
        directory = Path(__file__).resolve().parents[4] / '.runtime' / 'study-scope-backups'
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = directory / f'before-study-scope-{stamp}-{uuid4().hex[:8]}.db'
        with closing(sqlite3.connect(Path(engine.url.database).resolve().as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(backup)) as target:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('清理前备份校验失败，未更改原库。')
    with engine.begin() as db:
        if retired_questions:
            questions = 'SELECT id FROM lab_questions WHERE topic IN (7,8)'
            attempts = f'SELECT id FROM lab_attempts WHERE question_id IN ({questions})'
            for table in ('grade_drafts', 'grade_audits'):
                if table in tables:
                    db.execute(text(f'DELETE FROM {table} WHERE attempt_id IN ({attempts})'))
            if 'lab_attempts' in tables:
                db.execute(text(f'DELETE FROM lab_attempts WHERE question_id IN ({questions})'))
            for table in ('question_revisions', 'question_workspaces'):
                if table in tables:
                    db.execute(text(f'DELETE FROM {table} WHERE question_id IN ({questions})'))
            db.execute(text('DELETE FROM lab_questions WHERE topic IN (7,8)'))
        for table in retired_tables:
            db.execute(text(f'DROP TABLE {table}'))
    return {'backup': backup, 'removed_questions': retired_questions, 'removed_tables': retired_tables}
