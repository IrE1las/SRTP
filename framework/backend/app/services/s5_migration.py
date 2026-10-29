"""Explicit additive S5 migration with backup and preserved old-table checks."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from sqlalchemy import create_engine, inspect
from app.models.exam import Exam, ExamParticipant, ExamAttempt, ExamControlEvent

MODELS = [Exam, ExamParticipant, ExamAttempt, ExamControlEvent]
TABLES = {model.__tablename__ for model in MODELS}


def require_exam_schema(engine):
    tables = set(inspect(engine).get_table_names())
    if 'users' in tables and not TABLES <= tables:
        raise RuntimeError('数据库尚未升级S5。请先停服并运行 scripts/migrate_s5.py --database <数据库路径> 预览，再加 --apply 显式迁移。')


def old_fingerprints(path):
    with sqlite3.connect(f'file:{Path(path).as_posix()}?mode=ro', uri=True) as connection:
        names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                 if r[0] not in TABLES and not r[0].startswith('sqlite_')]
        result = {}
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted((repr(row) for row in connection.execute(f'SELECT * FROM {quoted}')))
            result[name] = sha256('\n'.join(rows).encode()).hexdigest()
        return result


def migrate(path, apply=False):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('数据库不存在；新安装请直接启动创建空库')
    engine = create_engine('sqlite:///' + path.as_posix())
    existing = set(inspect(engine).get_table_names())
    missing = sorted(TABLES - existing)
    result = {'stage': 'S5', 'database': str(path), 'missing_tables': missing, 'applied': False}
    if not apply or not missing:
        engine.dispose()
        return result
    from app.services.s1_migration import require_current_schema
    from app.services.s2_migration import require_account_schema
    require_current_schema(engine)
    require_account_schema(engine)
    from app.services.s3_migration import require_operation_schema
    require_operation_schema(engine)
    from app.services.s4_migration import require_learning_schema
    require_learning_schema(engine)
    before = old_fingerprints(path)
    root = Path(__file__).resolve().parents[4]
    backup_dir = root / '.runtime/backups/s5'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = backup_dir / f'{path.stem}-{stamp}-{uuid4().hex[:8]}.db'
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql('BEGIN IMMEDIATE')
            try:
                for model in MODELS:
                    model.__table__.create(conn, checkfirst=True)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        if old_fingerprints(path) != before:
            raise RuntimeError('旧数据核对不一致；备份已保留，请停止服务检查')
        result.update(applied=True, backup=str(backup), preserved_original_tables=True)
        backup.with_suffix('.manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
        return result
    finally:
        engine.dispose()
