"""Idempotent initialization of retained teaching sources; no legacy seeds."""
import json
from app.models import LabQuestion, ShuntingDataset
from app.services.lab_topics import ROOT, import_topics
from app.services.shunting_data import DATASET_KEY, import_reviewed_routes

def seed_theory(db):
    report = {}
    try:
        if db.query(ShuntingDataset).filter_by(dataset_key=DATASET_KEY).first() is None:
            payload = json.loads((ROOT / 'ai_design/station/shunting_interlocking_reviewed.json').read_text('utf8'))
            report['shunting'] = import_reviewed_routes(db, payload)
        if db.query(LabQuestion).count() == 0:
            report['theory'] = import_topics(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return report or {'status':'already_initialized'}
