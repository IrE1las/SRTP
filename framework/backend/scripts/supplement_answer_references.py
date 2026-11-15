"""Version existing report questions with locally sourced essay explanations."""
import argparse
import copy
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.database import SessionLocal, engine
from app.models import LabQuestion, QuestionWorkspace, QuestionRevision
from app.services.lab_topics import resolve_blueprint, digest
from app.services.question_authoring import claim_revision


def without_manual_explanations(item):
    result = copy.deepcopy(item)
    for f in result['fields']:
        if f['kind'] == 'essay':
            f.pop('explanation', None)
    return result


def prepare(db):
    _, resolved = resolve_blueprint(db)
    updates = []
    for item in resolved:
        q = db.query(LabQuestion).filter_by(key=item['key']).one()
        state = db.get(QuestionWorkspace, q.id)
        if q.content == item:
            continue
        if state is None or state.draft is not None or state.status != 'published':
            raise ValueError(f'{q.key}存在未发布修改或不是已发布状态，未覆盖')
        if without_manual_explanations(q.content) != without_manual_explanations(item):
            raise ValueError(f'{q.key}已发生其他内容修改，未覆盖')
        if any(f.get('explanation') for f in q.content['fields'] if f['kind']=='essay'):
            raise ValueError(f'{q.key}已有其他人工解析，未覆盖')
        updates.append((q, state, item))
    return updates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(engine.url.database).resolve()
    if engine.url.get_backend_name() != 'sqlite' or not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('数据库须是项目内已有SQLite文件')
    with SessionLocal() as db:
        pending = len(prepare(db))
    result = {'database': str(path), 'pending_questions': pending, 'applied': False}
    if args.apply and pending:
        backup = ROOT / 'outputs/backups' / datetime.now().strftime('answer-references-%Y%m%d-%H%M%S-%f') / 'railway.db'
        backup.parent.mkdir(parents=True)
        with sqlite3.connect(path) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        versions = []
        with SessionLocal.begin() as db:
            for q, state, item in prepare(db):
                claim_revision(db, state, state.revision, None)
                q.content = copy.deepcopy(item)
                q.fingerprint = digest(item)
                state.published_version += 1
                db.add(QuestionRevision(question_id=q.id, version=state.published_version,
                    content=copy.deepcopy(item), note='依据本地资料补充参考解答；保留实验与电路资料缺口'))
                versions.append({'key': q.key, 'version': state.published_version})
        result.update(applied=True, backup=str(backup), versions=versions)
        (backup.parent / 'supplement.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
