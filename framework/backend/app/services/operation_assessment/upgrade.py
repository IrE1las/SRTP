"""Additive SQLite upgrade with a checked, workspace-local consistent backup."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4
from sqlalchemy import inspect

ROOT = Path(__file__).resolve().parents[5]
TABLES = ['operation_assessment_configs', 'operation_evidence_events', 'exam_evidence_seals',
          'exam_evaluations', 'exam_assessment_reviews', 'exam_student_commentaries',
          'exam_assessment_review_history', 'exam_published_assessments']


def upgrade(engine):
    from app.core.database import Base
    import app.models  # register the additive tables
    existing = set(inspect(engine).get_table_names())
    if all(name in existing for name in TABLES):
        return {'changed': False}
    backup = None
    with engine.connect() as connection:
        retained = {name: connection.exec_driver_sql('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').scalar()
                    for name in existing}
    if engine.dialect.name == 'sqlite' and engine.url.database not in (None, ':memory:') and existing:
        original = Path(engine.url.database).resolve()
        if not original.is_relative_to(ROOT):
            raise RuntimeError('操作考试升级的数据库不在项目范围内，未进行修改')
        directory = ROOT / '.runtime' / 'exam-backups'
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / ('before-assessment-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8] + '.db')
        source = sqlite3.connect(original.as_uri() + '?mode=ro', uri=True)
        try:
            with sqlite3.connect(target) as copy:
                source.backup(copy)
                if copy.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('操作考试升级备份校验失败，未升级数据库')
                backup = str(target)
        finally:
            source.close()
    for name in TABLES:
        Base.metadata.tables[name].create(engine, checkfirst=True)
    with engine.connect() as connection:
        after = {name: connection.exec_driver_sql('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').scalar()
                 for name in existing}
    if retained != after:
        raise RuntimeError('升级期间原数据数量发生变化，请核对备份；未删除或覆盖原数据')
    return {'changed': True, 'backup': backup}
