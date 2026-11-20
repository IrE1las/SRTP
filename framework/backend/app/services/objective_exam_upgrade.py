"""Generalize attempt IDs without changing existing attempts or their children."""
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3
from uuid import uuid4
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable, CreateIndex

ROOT = Path(__file__).resolve().parents[4]


def upgrade(engine):
    inspector = inspect(engine)
    if 'exam_attempts' not in inspector.get_table_names() or not any(
        fk['referred_table'] == 'operation_sessions' for fk in inspector.get_foreign_keys('exam_attempts')
    ):
        return {'changed': False}
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('客观题考试升级当前仅支持SQLite')
    backup = None
    if engine.url.database not in (None, ':memory:'):
        original = Path(engine.url.database).resolve()
        if not original.is_relative_to(ROOT):
            raise RuntimeError('考试数据库不在项目范围内，未升级')
        directory = ROOT / '.runtime/exam-backups'
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / ('before-objective-exams-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8] + '.db')
        with closing(sqlite3.connect(original.as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(target)) as copy:
                source.backup(copy)
                if copy.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('考试升级前备份校验失败')
        backup = str(target)
    from app.models.exam import ExamAttempt
    table = ExamAttempt.__table__
    raw = engine.raw_connection()
    enabled = 0
    try:
        cursor = raw.cursor()
        enabled = cursor.execute('PRAGMA foreign_keys').fetchone()[0]
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute('BEGIN IMMEDIATE')
        violations = set(cursor.execute('PRAGMA foreign_key_check').fetchall())
        tables = inspector.get_table_names()
        quote = lambda name: '"' + name.replace('"', '""') + '"'
        counts = {name: cursor.execute('SELECT COUNT(*) FROM ' + quote(name)).fetchone()[0] for name in tables}
        old = cursor.execute('SELECT * FROM exam_attempts ORDER BY session_id').fetchall()
        sql = str(CreateTable(table).compile(engine)).replace('CREATE TABLE exam_attempts', 'CREATE TABLE objective_attempt_upgrade', 1)
        cursor.execute(sql)
        columns = ','.join(quote(column.name) for column in table.columns)
        cursor.execute(f'INSERT INTO objective_attempt_upgrade ({columns}) SELECT {columns} FROM exam_attempts')
        cursor.execute('DROP TABLE exam_attempts')
        cursor.execute('ALTER TABLE objective_attempt_upgrade RENAME TO exam_attempts')
        for index in table.indexes:
            cursor.execute(str(CreateIndex(index).compile(engine)))
        if old != cursor.execute('SELECT * FROM exam_attempts ORDER BY session_id').fetchall():
            raise RuntimeError('考试升级数据核对失败')
        if counts != {name: cursor.execute('SELECT COUNT(*) FROM ' + quote(name)).fetchone()[0] for name in tables}:
            raise RuntimeError('考试升级原数据数量核对失败')
        if set(cursor.execute('PRAGMA foreign_key_check').fetchall()) - violations:
            raise RuntimeError('考试升级关联校验失败')
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.cursor().execute('PRAGMA foreign_keys=' + str(enabled))
        raw.close()
    return {'changed': True, 'backup': backup}
