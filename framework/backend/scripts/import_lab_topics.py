"""Validate report-derived topics; --apply backs up SQLite before importing."""
import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.database import SessionLocal, engine
from app.models import LabAttempt, LabQuestion
from app.services.lab_topics import ROOT, import_topics, resolve_blueprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    db_path = Path(engine.url.database).resolve()
    if engine.url.get_backend_name() != 'sqlite' or not db_path.is_relative_to(ROOT) or not db_path.is_file():
        raise ValueError('仅允许导入 SRTP 项目内已存在的 SQLite 数据库')
    with SessionLocal() as db:
        dataset, questions = resolve_blueprint(db)
        report = {'mode':'validate','database':str(db_path),'dataset_id':dataset.id,
                  'topics':8,'questions':len(questions),
                  'automatic_fields':sum(f['kind']!='essay' for q in questions for f in q['fields']),
                  'manual_fields':sum(f['kind']=='essay' for q in questions for f in q['fields'])}
    if args.apply:
        backup = ROOT/'outputs/backups'/datetime.now().strftime('report-topics-%Y%m%d-%H%M%S-%f')/'railway.db'
        backup.parent.mkdir(parents=True)
        # SQLite backup also includes committed WAL data if an app is running.
        with sqlite3.connect(db_path) as source, sqlite3.connect(backup) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('备份完整性校验失败')
        LabQuestion.__table__.create(engine, checkfirst=True)
        LabAttempt.__table__.create(engine, checkfirst=True)
        with SessionLocal() as db, db.begin():
            report.update(import_topics(db))
        report.update(mode='apply',backup=str(backup))
        (backup.parent/'import-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
