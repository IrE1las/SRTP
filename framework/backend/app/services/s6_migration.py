"""Explicit, backed-up additive migration for manual exam grades."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from uuid import uuid4
from sqlalchemy import create_engine, inspect
from app.models.exam_grade import ExamGrade, ExamGradePublication, ExamGradeAudit

MODELS = [ExamGrade, ExamGradePublication, ExamGradeAudit]
TABLES = {model.__tablename__ for model in MODELS}


def require_grade_schema(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if 'users' not in tables:
        return
    for model in MODELS:
        name = model.__tablename__
        if name not in tables or not set(model.__table__.columns.keys()) <= {col['name'] for col in inspector.get_columns(name)}:
            raise RuntimeError('数据库尚未升级S6或成绩表结构不完整。请先停服并运行 scripts/migrate_s6.py --database <数据库路径> 预览，再加 --apply 显式迁移。')


def fingerprints(path):
    # Include every pre-existing table, including frozen S5 exam records.
    from hashlib import sha256
    result = {}
    with sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True) as connection:
        for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            if name in TABLES:
                result.pop(name, None)
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(repr(row) for row in connection.execute(f'SELECT * FROM {quoted}'))
            result[name] = sha256('\n'.join(rows).encode()).hexdigest()
    return result


def migrate(path, apply=False):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('数据库不存在；新安装请直接启动创建空库')
    engine = create_engine('sqlite:///' + path.as_posix())
    try:
        inspector = inspect(engine)
        existing = set(inspector.get_table_names())
        missing = sorted(TABLES - existing)
        for model in MODELS:
            name = model.__tablename__
            if name in existing and not set(model.__table__.columns.keys()) <= {col['name'] for col in inspector.get_columns(name)}:
                raise RuntimeError('现有S6表结构不完整，请保留备份并人工检查，不能自动修补')
        result = {'stage': 'S6', 'database': str(path), 'missing_tables': missing, 'applied': False}
        if not apply or not missing:
            return result
        from app.services.s1_migration import require_current_schema
        from app.services.s2_migration import require_account_schema
        from app.services.s3_migration import require_operation_schema
        from app.services.s4_migration import require_learning_schema
        from app.services.s5_migration import require_exam_schema
        for check in (require_current_schema, require_account_schema, require_operation_schema,
                      require_learning_schema, require_exam_schema):
            check(engine)
        before = fingerprints(path)
        backup_dir = Path(__file__).resolve().parents[4] / '.runtime/backups/s6'
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = backup_dir / f'{path.stem}-{stamp}-{uuid4().hex[:8]}.db'
        with sqlite3.connect(path) as source, sqlite3.connect(backup) as destination:
            source.backup(destination)
        with engine.connect() as connection:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
            try:
                for model in MODELS:
                    model.__table__.create(connection, checkfirst=True)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        require_grade_schema(engine)
        if fingerprints(path) != before:
            raise RuntimeError('原数据核对不一致；备份已保留，请停止服务检查')
        result.update(applied=True, backup=str(backup), preserved_original_tables=True)
        backup.with_suffix('.manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
        return result
    finally:
        engine.dispose()
