"""Lossless workspace-local exports. Never deletes or mutates exam evidence."""
import gzip
import json
from pathlib import Path
from sqlalchemy import select
from app.models.exam import Exam
from app.models.operation import OperationEvent
from app.models.operation_assessment import ExamEvidenceSeal
from app.services.operation_assessment import evidence, service, scorer

ROOT = Path(__file__).resolve().parents[5]


def verify(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('归档必须位于项目目录内')
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        package = json.load(stream)
    if evidence.digest(package['payload']) != package['digest']:
        raise ValueError('归档内容哈希不一致')
    data = package['payload']
    previous = None
    for sequence, row in enumerate(data['evidence'], 1):
        if row['sequence'] != sequence or row['content']['previous_digest'] != previous or evidence.digest(row['content']) != row['digest']:
            raise ValueError('归档事件顺序或哈希不一致')
        previous = row['digest']
    seal = data['seal']
    if seal.get('evidence_count') != len(data['evidence']) or seal.get('evidence_digest') != previous or (
        seal.get('click_count') != len(data['clicks']) or seal.get('click_digest') != evidence.digest(data['clicks'])):
        raise ValueError('归档数量或封存摘要不一致')
    if data['evaluation']['status'] == 'ready':
        result = scorer.score(data['configuration'], data['evidence'], seal['final_state'])
        if evidence.digest(result) != evidence.digest({k:v for k,v in data['evaluation'].items() if k not in {'id','version','cutoff_at'}}):
            raise ValueError('从归档重新计算的评价不一致')
    return {'verified':True,'evidence_count':len(data['evidence']),'click_count':len(data['clicks']),
            'bytes':path.stat().st_size,'digest':package['digest']}


def export(db, user, sid):
    from app.services import exam_grades as grades, exams
    attempt = grades.reviewable(db,user,sid)
    if not grades.published(db,sid):
        raise ValueError('成绩发布后才能导出正式评分证据归档')
    seal = db.get(ExamEvidenceSeal,sid)
    evaluation = service.view(db,sid)
    if not seal or seal.content['status']!='ready' or not evaluation:
        raise ValueError('此答卷证据尚不完整，请先人工复核')
    rows=evidence.rows(db,sid)
    payload={'schema_version':1,'session_id':sid,'configuration':db.get(Exam,attempt.exam_id).question_snapshot['assessment'],
        'seal':seal.content,'evaluation':evaluation,
        'clicks':[r.content for r in db.scalars(select(OperationEvent).where(OperationEvent.session_id==sid).order_by(OperationEvent.sequence))],
        'evidence':[{'sequence':r.sequence,'content':r.content,'digest':r.digest} for r in rows]}
    package={'payload':payload,'digest':evidence.digest(payload)}
    db.commit()  # Release read transactions before compression and verification.
    directory=ROOT/'.runtime'/'exam-archives';directory.mkdir(parents=True,exist_ok=True)
    target=directory/(sid+'-'+package['digest'][:16]+'.json.gz')
    if not target.exists():
        # Unique staging path makes interrupted exports unable to replace a verified archive.
        from uuid import uuid4
        staged=directory/(target.name+'.'+uuid4().hex+'.tmp')
        try:
            with gzip.open(staged,'wt',encoding='utf-8') as stream:
                json.dump(package,stream,ensure_ascii=False,separators=(',',':'))
            verify(staged)
            staged.replace(target)
        finally:
            staged.unlink(missing_ok=True)
    return {'filename':target.name,**verify(target)}
