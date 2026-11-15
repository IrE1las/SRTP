"""Append only real submissions/commands; never reconstruct missing history."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func
from app.models.learning_archive import LearningArchive, LearningArchiveEvent


def now():
    return datetime.now(timezone.utc)


def without_secrets(value):
    if isinstance(value, dict):
        return {key: without_secrets(item) for key, item in value.items()
                if str(key).lower() not in {'pin', 'password', 'token', 'api_key'}}
    if isinstance(value, list):
        return [without_secrets(item) for item in value]
    return deepcopy(value)


def fingerprint(answer):
    return sha256(json.dumps(answer, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def start_console(db, user, snapshot, source):
    archive = LearningArchive(id=snapshot['session_id'], owner_id=user.id, kind='simulation',
        title='标准站仿真操作' if source == 'reference' else '教学站仿真操作', status='recorded',
        preview=user.role != 'student', data={'source': source},
        initial_snapshot=without_secrets(snapshot), latest_snapshot=without_secrets(snapshot))
    db.add(archive)
    db.commit()


def append_console(db, user, session_id, command, before, response):
    archive = db.query(LearningArchive).filter_by(id=session_id, owner_id=user.id, kind='simulation').first()
    # Sessions created by old code have no earlier durable evidence. Start at the
    # first observed command and label this limitation, without inventing events.
    if archive is None:
        archive = LearningArchive(id=session_id, owner_id=user.id, kind='simulation',
            title='仿真操作（从本次操作开始记录）', status='recorded', preview=user.role != 'student',
            data={'partial_history': True}, initial_snapshot=without_secrets(before), latest_snapshot={})
        db.add(archive)
        db.flush()
    sequence = (db.query(func.max(LearningArchiveEvent.sequence)).filter_by(archive_id=session_id).scalar() or 0) + 1
    event = LearningArchiveEvent(id=str(uuid4()), archive_id=archive.id, sequence=sequence,
        command=without_secrets(command), response=without_secrets(response), before_snapshot=without_secrets(before))
    db.add(event)
    archive.latest_snapshot = without_secrets(response.get('snapshot', before))
    archive.updated_at = now()
    db.commit()


def save_classic(db, user, answer, comparison, title):
    archive = LearningArchive(id=str(uuid4()), owner_id=user.id, kind='classic', title=title,
        status='submitted', preview=user.role != 'student',
        data={'answer': answer, 'answer_fingerprint': fingerprint(answer), 'comparison': comparison})
    db.add(archive)
    db.commit()
    return archive.id


def find_classic_explanation_target(db, user, record_id, answer):
    if not record_id:
        return None
    archive = db.query(LearningArchive).filter_by(id=record_id, owner_id=user.id, kind='classic').first()
    if archive is None:
        raise HTTPException(404, '提交记录不存在')
    if archive.data.get('answer_fingerprint') != fingerprint(answer):
        raise HTTPException(409, '解析答案与该提交记录不一致，请重新提交后再解析')
    return archive


def attach_explanation(db, archive, explanation):
    if archive is None:
        return
    timestamp = now()
    archive.feedback = [*archive.feedback, {'source': explanation['source'],
        'title': {'ai': 'AI解析', 'rules_fallback': '本地规则解析', 'no_errors': '作答核对'}.get(explanation['source'], '教学反馈'),
        'text': explanation['ai_explanation'], 'time': timestamp.isoformat()}]
    archive.updated_at = timestamp
    db.commit()
