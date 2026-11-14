"""Report-topic student workflow and explicit teacher marking."""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.lab_topic import LabAttempt, LabQuestion
from app.models.user import User
from app.models.authoring import QuestionWorkspace
from sqlalchemy import or_
from app.services.grading import grade_etag, save_grade
from app.services.lab_topics import attempt_view, evaluate, public_question

router = APIRouter()
reader = require_roles('student','teacher','admin')
teacher = require_roles('teacher','admin')


class Submission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fingerprint: str = Field(min_length=64,max_length=64)
    answers: dict[str, Any] = Field(max_length=30)


class Marking(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scores: dict[str, StrictInt] = Field(max_length=30)
    comment: str = Field(min_length=1,max_length=6000)


def find_question(db, key, published=True):
    q = db.query(LabQuestion).filter_by(key=key).one_or_none()
    if q is None: raise HTTPException(404,'专题题目不存在')
    state=db.get(QuestionWorkspace,q.id)
    if published and state is not None and state.status!='published':raise HTTPException(404,'题目未发布或已停用')
    return q


@router.get('/questions')
def questions(db: Session=Depends(get_db), user: User=Depends(reader)):
    query=db.query(LabQuestion).outerjoin(QuestionWorkspace).filter(or_(QuestionWorkspace.question_id.is_(None),QuestionWorkspace.status=='published'))
    return [public_question(q,detail=False) for q in query.order_by(LabQuestion.topic,LabQuestion.sequence,LabQuestion.id)]


@router.get('/attempts')
def own_attempts(db: Session=Depends(get_db), user: User=Depends(reader)):
    return [attempt_view(a) for a in db.query(LabAttempt).filter_by(student_id=user.id).order_by(LabAttempt.id.desc()).limit(200)]


@router.get('/reviews')
def reviews(db: Session=Depends(get_db), user: User=Depends(teacher)):
    pairs = db.query(LabAttempt,User).join(User,User.id==LabAttempt.student_id).order_by(LabAttempt.id.desc()).limit(300).all()
    return [{**attempt_view(a),'student_name':u.real_name or u.username,
             'rubric':[{'id':f['id'],'label':f['label'],'points':f['points'],'criteria':f.get('criteria',[])}
                       for f in a.question_snapshot['fields'] if f['kind']=='essay'],
             'source_section':a.question_snapshot['source_section'],
             'report':a.question_snapshot['topic_info']['report']} for a,u in pairs]


@router.get('/questions/{key}')
def question_detail(key: str, db: Session=Depends(get_db), user: User=Depends(reader)):
    return public_question(find_question(db,key))


@router.get('/questions/{key}/rubric')
def question_rubric(key: str, db: Session=Depends(get_db), user: User=Depends(teacher)):
    return find_question(db,key,published=False).content


@router.post('/questions/{key}/submit', status_code=201)
def submit(key: str, body: Submission, db: Session=Depends(get_db), user: User=Depends(reader)):
    question = find_question(db,key)
    if body.fingerprint != question.fingerprint:
        raise HTTPException(409,'题目已更新，请刷新后重新核对作答')
    try:
        result = evaluate(question.content,body.answers)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    attempt = LabAttempt(question_id=question.id,student_id=user.id,question_snapshot=question.content,answers=body.answers,result=result)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt_view(attempt)


@router.post('/attempts/{attempt_id}/review')
def mark(attempt_id: int, body: Marking, db: Session=Depends(get_db), user: User=Depends(teacher)):
    attempt = db.get(LabAttempt,attempt_id)
    if attempt is None: raise HTTPException(404,'作答记录不存在')
    if attempt.review is not None: raise HTTPException(409,'本次作答已评阅，请勿重复提交')
    manual = {f['id']:f for f in attempt.question_snapshot['fields'] if f['kind']=='essay'}
    if not manual or set(body.scores)!=set(manual) or not body.comment.strip():
        raise HTTPException(422,'请对每个论述栏评分并填写评语')
    if any(score<0 or score>manual[fid]['points'] for fid,score in body.scores.items()):
        raise HTTPException(422,'评分超出本栏分值')
    try:save_grade(db,attempt,user.id,body.model_dump(),grade_etag(attempt))
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    db.commit()
    return attempt_view(attempt)
