"""Generate the original-station shunting question pool with a recovery snapshot."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, engine
from app.models.shunting_route import ShuntingQuestion, ShuntingRoute
from app.services.shunting_questions import generate_shunting_questions, get_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='写入题目表；默认只检查是否可生成')
    parser.add_argument('--backup-dir', type=Path, help='数据库备份目录，必须位于项目根目录内')
    args = parser.parse_args()

    if not args.apply:
        with SessionLocal() as db:
            dataset = get_dataset(db)
            route_count = db.query(ShuntingRoute).filter_by(dataset_id=dataset.id).count()
            print(json.dumps({
                'validated': True,
                'dataset_id': dataset.id,
                'station_key': dataset.station_key,
                'route_count': route_count,
                'existing_questions': db.query(ShuntingQuestion).filter_by(dataset_id=dataset.id).count(),
                'applied': False,
            }, ensure_ascii=False))
        return

    if args.backup_dir is None:
        parser.error('--apply requires --backup-dir')
    backup_dir = args.backup_dir.resolve()
    if not backup_dir.is_relative_to(ROOT):
        parser.error('Backup directory must be inside the project')
    if engine.url.get_backend_name() != 'sqlite':
        parser.error('This local generation command requires SQLite')
    database = Path(engine.url.database).resolve()
    if database != BACKEND / 'railway.db':
        parser.error('Database does not match the active project database')
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / 'railway-before-apply.db'
    if backup_file.exists():
        parser.error('Backup already exists; use a new backup directory')
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(backup_file) as dst:
            src.backup(dst)
    ShuntingQuestion.__table__.create(engine, checkfirst=True)
    with SessionLocal.begin() as db:
        result = generate_shunting_questions(db)
    result.update({'applied': True, 'database': str(database), 'backup': str(backup_file)})
    (backup_dir / 'generation-result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
