"""Initialize a fresh local SQLite database with the reviewed teaching data.

Safe to run repeatedly: imports are skipped when the target tables already
contain rows. Called by the project launcher after the backend becomes ready.
"""

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, engine
from app.models import LabQuestion
from app.models.shunting_route import ShuntingDataset
from app.services.lab_topics import import_topics, resolve_blueprint
from app.services.shunting_data import import_reviewed_routes, validate_payload

SHUNTING_PAYLOAD = ROOT / 'ai_design/station/shunting_interlocking_reviewed.json'


def main() -> None:
    if engine.url.get_backend_name() != 'sqlite':
        raise ValueError('Local data bootstrap only supports SQLite.')
    payload = json.loads(SHUNTING_PAYLOAD.read_text(encoding='utf-8'))
    validate_payload(payload)
    report = {}
    with SessionLocal() as db:
        need_shunting = db.query(ShuntingDataset).count() == 0
        need_lab = db.query(LabQuestion).count() == 0
    if need_shunting:
        with SessionLocal() as db, db.begin():
            report['shunting'] = import_reviewed_routes(db, payload)
    else:
        report['shunting'] = 'skipped (already present)'
    if need_lab:
        with SessionLocal() as db:
            _, questions = resolve_blueprint(db)
        with SessionLocal() as db, db.begin():
            report['lab_topics'] = import_topics(db)
    else:
        report['lab_topics'] = 'skipped (already present)'
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
