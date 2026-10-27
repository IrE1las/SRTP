"""Report-topic student workflow and explicit teacher marking."""
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.lab_topic import LabAttempt, LabQuestion
from app.models.user import User
from app.models.authoring import QuestionWorkspace
from sqlalchemy import or_, func, case
from app.services.grading import grade_etag, save_grade
from app.services.lab_topics import RETAINED_KEYS, attempt_view, evaluate, public_question

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
    q = db.query(LabQuestion).filter(LabQuestion.key == key, LabQuestion.key.in_(RETAINED_KEYS), LabQuestion.topic.between(1,6)).one_or_none()
    if q is None: raise HTTPException(404,'专题题目不存在')
    state=db.get(QuestionWorkspace,q.id)
    if published and state is not None and state.status!='published':raise HTTPException(404,'题目未发布或已停用')
    return q


@router.get('/questions')
def questions(db: Session=Depends(get_db), user: User=Depends(reader)):
    query=db.query(LabQuestion).filter(LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic.between(1,6)).outerjoin(QuestionWorkspace).filter(or_(QuestionWorkspace.question_id.is_(None),QuestionWorkspace.status=='published'))
    return [public_question(q,detail=False) for q in query.order_by(LabQuestion.topic,LabQuestion.sequence,LabQuestion.id)]


@router.get('/attempts')
def own_attempts(topic: int=Query(...,ge=1,le=6), db: Session=Depends(get_db), user: User=Depends(reader)):
    return [attempt_view(a) for a in db.query(LabAttempt).join(LabQuestion).filter(LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic==topic,LabAttempt.student_id==user.id).order_by(LabAttempt.id.desc()).limit(200)]



@router.get('/attempts/page')
def own_attempt_page(topic:int=Query(...,ge=1,le=6),page:int=Query(1,ge=1),
                     page_size:int=Query(6,ge=6,le=6),db:Session=Depends(get_db),user:User=Depends(reader)):
    query=db.query(LabAttempt).join(LabQuestion).filter(
        LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic==topic,LabAttempt.student_id==user.id)
    total=query.count()
    page_count=max(1,(total+page_size-1)//page_size)
    page=min(page,page_count)
    rows=query.order_by(LabAttempt.created_at.desc(),LabAttempt.id.desc()).offset((page-1)*page_size).limit(page_size)
    return {'items':[{'id':a.id,'question_title':a.question_snapshot['title'],'topic':a.question_snapshot['topic'],
                      'created_at':a.created_at,'result':{key:a.result.get(key) for key in
                        ('status','automatic_score','automatic_max','total_score','total_max')}} for a in rows],
            'total':total,'page':page,'page_size':page_size,'page_count':page_count}

@router.get('/attempts/{attempt_id}')
def own_attempt_detail(attempt_id:int,db:Session=Depends(get_db),user:User=Depends(reader)):
    attempt=db.query(LabAttempt).join(LabQuestion).filter(
        LabAttempt.id==attempt_id,LabAttempt.student_id==user.id,
        LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic.between(1,6)).one_or_none()
    if attempt is None:
        raise HTTPException(404,'本人六专题作答不存在')
    return attempt_view(attempt)


@router.get('/reviews')
def reviews(topic: int=Query(...,ge=1,le=6), db: Session=Depends(get_db), user: User=Depends(teacher)):
    pairs = db.query(LabAttempt,User).join(User,User.id==LabAttempt.student_id).join(LabQuestion,LabQuestion.id==LabAttempt.question_id).filter(LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic==topic).order_by(LabAttempt.id.desc()).limit(300).all()
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
    if attempt is None or attempt.question_snapshot.get("key") not in RETAINED_KEYS or attempt.question_snapshot.get("topic") not in range(1,7): raise HTTPException(404,'作答记录不存在')
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


def student_identity(user):
    return {'id':user.id,'student_name':user.real_name or None,'username':user.username,
            'student_number':user.student_id or None,'class_name':user.class_name or None}

def review_attempt(db,attempt_id):
    attempt=db.query(LabAttempt).join(LabQuestion).filter(
        LabAttempt.id==attempt_id,LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic.between(1,6)
    ).one_or_none()
    if attempt is None or attempt.question_snapshot.get('key') not in RETAINED_KEYS:
        raise HTTPException(404,'六专题作答不存在')
    return attempt

@router.get('/review-students')
def review_students(topic:int|None=Query(None,ge=1,le=6),db:Session=Depends(get_db),user:User=Depends(teacher)):
    query=db.query(LabAttempt.student_id,func.count(LabAttempt.id),
                   func.sum(case((LabAttempt.result['status'].as_string()=='pending_review',1),else_=0)),
                   func.max(LabAttempt.created_at)).join(LabQuestion).filter(
                       LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic.between(1,6))
    if topic is not None:
        query=query.filter(LabQuestion.topic==topic)
    totals={row[0]:row[1:] for row in query.group_by(LabAttempt.student_id)}
    people=db.query(User).filter(User.role=='student').order_by(User.class_name,User.student_id,User.id).all()
    return [{**student_identity(person),'attempt_count':totals.get(person.id,(0,0,None))[0],
             'pending_count':totals.get(person.id,(0,0,None))[1] or 0,
             'latest_submission':totals.get(person.id,(0,0,None))[2]} for person in people]

@router.get('/review-students/{student_id}/attempts')
def student_attempts(student_id:int,topic:int|None=Query(None,ge=1,le=6),
                     db:Session=Depends(get_db),user:User=Depends(teacher)):
    student=db.query(User).filter_by(id=student_id,role='student').one_or_none()
    if student is None:
        raise HTTPException(404,'学生不存在')
    query=db.query(LabAttempt.id,LabQuestion.topic,LabAttempt.question_snapshot['title'].as_string(),
                   LabAttempt.created_at,LabAttempt.result['status'].as_string()).join(LabQuestion).filter(
                       LabAttempt.student_id==student_id,LabQuestion.key.in_(RETAINED_KEYS),LabQuestion.topic.between(1,6))
    if topic is not None:
        query=query.filter(LabQuestion.topic==topic)
    return {'student':student_identity(student),'attempts':[
        {'id':row[0],'topic':row[1],'question_title':row[2],'created_at':row[3],'status':row[4]}
        for row in query.order_by(LabAttempt.created_at.desc(),LabAttempt.id.desc())]}

@router.get('/review-attempts/{attempt_id}')
def review_detail(attempt_id:int,db:Session=Depends(get_db),user:User=Depends(teacher)):
    attempt=review_attempt(db,attempt_id)
    student=db.get(User,attempt.student_id)
    return {**attempt_view(attempt),'student':student_identity(student),'question':attempt.question_snapshot,
            'rubric':[{'id':f['id'],'label':f['label'],'points':f['points'],'criteria':f.get('criteria',[])}
                      for f in attempt.question_snapshot['fields'] if f['kind']=='essay']}
