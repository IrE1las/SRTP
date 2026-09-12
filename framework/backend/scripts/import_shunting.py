"""Import the reviewed original-station table with a SQLite recovery snapshot."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, engine
from app.models.shunting_route import ShuntingDataset, ShuntingRoute
from app.services.shunting_data import import_reviewed_routes, validate_payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, default=ROOT/'ai_design/station/shunting_interlocking_reviewed.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-dir', type=Path)
    args = parser.parse_args()
    payload = json.loads(args.payload.read_text(encoding='utf-8'))
    validate_payload(payload)
    if not args.apply:
        print(json.dumps({'validated':True, 'routes':len(payload['routes']), 'applied':False},ensure_ascii=False))
        return
    if args.backup_dir is None:
        parser.error('--apply requires --backup-dir')
    backup_dir = args.backup_dir.resolve()
    if not backup_dir.is_relative_to(ROOT):
        parser.error('Backup directory must be inside the project')
    if engine.url.get_backend_name() != 'sqlite':
        parser.error('This local import command requires SQLite')
    database = Path(engine.url.database).resolve()
    if database != BACKEND/'railway.db':
        parser.error('Database does not match the active project database')
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir/'railway-before-apply.db'
    if backup_file.exists():
        parser.error('Backup already exists; use a new backup directory')
    with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as src:
        with sqlite3.connect(backup_file) as dst:
            src.backup(dst)
    ShuntingDataset.__table__.create(engine, checkfirst=True)
    ShuntingRoute.__table__.create(engine, checkfirst=True)
    with SessionLocal.begin() as db:
        result = import_reviewed_routes(db, payload)
    result.update({'applied':True, 'database':str(database), 'backup':str(backup_file)})
    (backup_dir/'import-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
