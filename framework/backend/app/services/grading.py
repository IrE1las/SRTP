"""Manual grading with rubric totals, optimistic writes and a revision trail."""
import copy
import math
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import update

from app.models import GradeAudit, GradeDraft, LabAttempt
from app.services.lab_topics import digest


def grade_etag(attempt):
    return digest({'review':attempt.review,'result':attempt.result,
                   'reviewed_at':attempt.reviewed_at.isoformat() if attempt.reviewed_at else None})


def score(value, maximum):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=maximum or round(value,2)!=value:
        raise ValueError(f'分数须在0至{maximum}之间，最多两位小数')
    return value


def validate_grade(attempt,raw):
    manual={f['id']:f for f in attempt.question_snapshot['fields'] if f['kind']=='essay'}
    scores=raw.get('scores',{})
    parts=raw.get('rubric_scores',{})
    comments=raw.get('field_comments',{})
    if not manual:raise ValueError('此作答没有待人工评分项目')
    if not isinstance(scores,dict) or set(scores)!=set(manual):raise ValueError('请逐栏完成评分')
    if not isinstance(parts,dict) or set(parts)-set(manual):raise ValueError('评分细则不属于本题')
    if not isinstance(comments,dict) or set(comments)-set(manual):raise ValueError('逐栏评语不属于本题')
    normalized,weighted,remarks={},{},{}
    for fid,f in manual.items():
        normalized[fid]=score(scores[fid],f['points'])
        rubric=f.get('rubric',[])
        if rubric:
            values=parts.get(fid,{})
            if not isinstance(values,dict) or set(values)!={r['id'] for r in rubric}:raise ValueError('请完成每项评分细则')
            weighted[fid]={r['id']:score(values[r['id']],r['points']) for r in rubric}
            if abs(sum(weighted[fid].values())-normalized[fid])>0.001:raise ValueError('细则分数合计与本栏分数不一致')
        elif fid in parts and parts[fid]:raise ValueError('此栏未定义分项评分细则')
        comment=comments.get(fid,'')
        if not isinstance(comment,str) or len(comment)>2000:raise ValueError('逐栏评语最多2000字')
        if comment.strip():remarks[fid]=comment.strip()
    comment=raw.get('comment','')
    if not isinstance(comment,str) or not comment.strip() or len(comment)>6000:raise ValueError('请填写总体评语，最多6000字')
    result={'scores':normalized,'comment':comment.strip()}
    if weighted:result['rubric_scores']=weighted
    if remarks:result['field_comments']=remarks
    return result


def save_grade(db,attempt,user_id,raw,etag,reason=''):
    if etag!=grade_etag(attempt):raise HTTPException(409,'此作答的成绩已更新，请重新加载后评阅')
    if not isinstance(reason,str) or len(reason)>1000:raise ValueError('更正原因最多1000字')
    if attempt.review is not None and not reason.strip():raise ValueError('修改已发布成绩时须填写更正原因')
    review=validate_grade(attempt,raw)
    result={**attempt.result,'status':'graded',
            'total_score':round(attempt.result['automatic_score']+sum(review['scores'].values()),2)}
    before={'review':copy.deepcopy(attempt.review),'result':copy.deepcopy(attempt.result),'reviewer_id':attempt.reviewer_id}
    previous=attempt.reviewed_at
    condition=LabAttempt.reviewed_at.is_(None) if previous is None else LabAttempt.reviewed_at==previous
    stamp=datetime.now(timezone.utc).replace(tzinfo=None)
    changed=db.execute(update(LabAttempt).where(LabAttempt.id==attempt.id,condition).values(
        review=review,result=result,reviewer_id=user_id,reviewed_at=stamp),execution_options={'synchronize_session':False})
    if changed.rowcount!=1:raise HTTPException(409,'评分保存冲突，请重新加载')
    db.add(GradeAudit(attempt_id=attempt.id,reviewer_id=user_id,before=before,
                     after={'review':review,'result':result},reason=reason.strip() or '首次评阅'))
    db.query(GradeDraft).filter_by(attempt_id=attempt.id,reviewer_id=user_id).delete()
    db.flush();db.refresh(attempt)
    return attempt
