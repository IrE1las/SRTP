"""Administrator question authoring and teacher/admin grading workbenches."""
import copy
import csv
import io
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import (LabQuestion, LabAttempt, User, QuestionWorkspace, QuestionRevision,
                        GradeDraft, GradeAudit, FeedbackSnippet)
from app.services.lab_topics import attempt_view, public_question, evaluate, digest
from app.services.question_authoring import (topic_catalog,validate_content,state_view,get_question,
                                             initialize_workspace,claim_revision,create_draft)
from app.services.grading import grade_etag,save_grade

router=APIRouter()
editor=require_roles('admin')
grader=require_roles('teacher','admin')


class Body(BaseModel):
    model_config=ConfigDict(extra='forbid')


class EditBody(Body):
    content:dict[str,Any]
    revision:StrictInt=Field(ge=0)


class NewBody(Body):
    content:dict[str,Any]


class RevisionBody(Body):
    revision:StrictInt=Field(ge=0)
    note:str=Field(default='',max_length=500)


class StatusBody(RevisionBody):
    status:Literal['published','archived']


class PreviewBody(NewBody):
    answers:dict[str,Any]|None=None


class ReviewBody(Body):
    etag:str=Field(min_length=64,max_length=64)
    scores:dict[str,Any]=Field(max_length=30)
    rubric_scores:dict[str,Any]=Field(default_factory=dict,max_length=30)
    field_comments:dict[str,str]=Field(default_factory=dict,max_length=30)
    comment:str=Field(max_length=6000)
    reason:str=Field(default='',max_length=1000)


class DraftBody(Body):
    content:dict[str,Any]


class SnippetBody(Body):
    text:str=Field(min_length=1,max_length=2000)


class BulkItem(Body):
    id:StrictInt=Field(gt=0)
    revision:StrictInt=Field(ge=0)


class BulkStatus(Body):
    items:list[BulkItem]=Field(min_length=1,max_length=100)
    status:Literal['published','archived']


def validation(operation):
    try:return operation()
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc


@router.get('/metadata')
def metadata(db:Session=Depends(get_db),user:User=Depends(grader)):
    from app.models import ShuntingDataset
    from app.services.shunting_data import DATASET_KEY
    dataset=db.query(ShuntingDataset).filter_by(dataset_key=DATASET_KEY).one_or_none()
    return {'topics':topic_catalog(),'topology':dataset.station_topology if dataset else None,
            'questions':[{'id':q.id,'title':q.content['title']} for q in db.query(LabQuestion).outerjoin(QuestionWorkspace).filter(func.coalesce(QuestionWorkspace.status,'published')!='draft').order_by(LabQuestion.topic,LabQuestion.sequence)],
            'classes':[r[0] for r in db.query(User.class_name).filter(User.class_name.is_not(None),User.class_name!='').distinct().order_by(User.class_name)]}


@router.get('/overview')
def overview(db:Session=Depends(get_db),user:User=Depends(grader)):
    rows=db.query(LabQuestion,QuestionWorkspace).outerjoin(QuestionWorkspace).all()
    return {'questions':len(rows),'published':sum(s is None or s.status=='published' for q,s in rows),
            'drafts':sum(s is not None and (s.draft is not None or s.status=='draft') for q,s in rows),
            'archived':sum(s is not None and s.status=='archived' for q,s in rows),
            'attempts':db.query(LabAttempt).count(),
            'pending':db.query(LabAttempt).filter(LabAttempt.result['status'].as_string()=='pending_review').count(),
            'graded':db.query(LabAttempt).filter(LabAttempt.result['status'].as_string()=='graded').count()}


@router.get('/questions')
def questions(search:str=Query('',max_length=150),topic:int|None=Query(None,ge=1,le=9),
              status:Literal['all','published','draft','archived']='all',page:int=Query(1,ge=1),
              limit:int=Query(20,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(editor)):
    query=db.query(LabQuestion,QuestionWorkspace).outerjoin(QuestionWorkspace)
    title=func.coalesce(QuestionWorkspace.draft['title'].as_string(),LabQuestion.content['title'].as_string())
    if search:query=query.filter(title.contains(search,autoescape=True))
    if topic:query=query.filter(func.coalesce(QuestionWorkspace.draft['topic'].as_integer(),LabQuestion.topic)==topic)
    if status=='draft':query=query.filter(or_(QuestionWorkspace.status=='draft',QuestionWorkspace.draft['title'].as_string().is_not(None)))
    elif status!='all':query=query.filter(func.coalesce(QuestionWorkspace.status,'published')==status)
    total=query.count()
    pairs=query.order_by(func.coalesce(QuestionWorkspace.updated_at,LabQuestion.created_at).desc(),LabQuestion.id.desc()).offset((page-1)*limit).limit(limit).all()
    return {'total':total,'items':[state_view(q,s) for q,s in pairs]}


@router.post('/questions',status_code=201)
def new_question(body:NewBody,db:Session=Depends(get_db),user:User=Depends(editor)):
    q,s=validation(lambda:create_draft(db,user.id,body.content));db.commit()
    return {**state_view(q,s),'content':s.draft}


@router.post('/questions/bulk-status')
def bulk_status(body:BulkStatus,db:Session=Depends(get_db),user:User=Depends(editor)):
    if len({x.id for x in body.items})!=len(body.items):raise HTTPException(422,'批量操作题目不能重复')
    for item in body.items:
        q=get_question(db,item.id);state=initialize_workspace(db,q)
        if body.status=='published' and not state.published_version:raise HTTPException(422,'所选题目含未发布草稿，请逐题预览并发布')
        claim_revision(db,state,item.revision,user.id);state.status=body.status
    db.commit();return {'updated':len(body.items)}


@router.post('/preview')
def preview(body:PreviewBody,db:Session=Depends(get_db),user:User=Depends(editor)):
    _,item=validation(lambda:validate_content(db,body.content,publish=True))
    item['key']='preview'
    q=LabQuestion(id=0,key='preview',content=item,fingerprint=digest(item))
    response={'question':public_question(q)}
    if body.answers is not None:response['result']=validation(lambda:evaluate(item,body.answers))
    return response


@router.get('/questions/{qid}')
def detail(qid:int,db:Session=Depends(get_db),user:User=Depends(editor)):
    q=get_question(db,qid);s=db.get(QuestionWorkspace,qid)
    return {**state_view(q,s),'content':s.draft if s and s.draft is not None else q.content}


@router.put('/questions/{qid}/draft')
def save_draft(qid:int,body:EditBody,db:Session=Depends(get_db),user:User=Depends(editor)):
    q=get_question(db,qid);s=initialize_workspace(db,q)
    _,item=validation(lambda:validate_content(db,body.content,previous=q.content))
    claim_revision(db,s,body.revision,user.id)
    item['key']=q.key;s.draft=item;db.commit()
    return {**state_view(q,s),'content':s.draft}


@router.post('/questions/{qid}/publish')
def publish(qid:int,body:RevisionBody,db:Session=Depends(get_db),user:User=Depends(editor)):
    q=get_question(db,qid);s=initialize_workspace(db,q)
    if s.draft is None:raise HTTPException(422,'请先保存题目草稿')
    _,item=validation(lambda:validate_content(db,s.draft,publish=True,previous=q.content))
    claim_revision(db,s,body.revision,user.id)
    item['key']=q.key;version=s.published_version+1
    q.content=item;q.topic=item['topic'];q.sequence=item['sequence'];q.fingerprint=digest(item)
    s.status='published';s.draft=None;s.published_version=version
    db.add(QuestionRevision(question_id=qid,version=version,content=copy.deepcopy(item),author_id=user.id,note=body.note or '发布题目'))
    db.commit();return state_view(q,s)


@router.post('/questions/{qid}/status')
def change_status(qid:int,body:StatusBody,db:Session=Depends(get_db),user:User=Depends(editor)):
    q=get_question(db,qid);s=initialize_workspace(db,q)
    if body.status=='published' and not s.published_version:raise HTTPException(422,'此题尚未发布，请先完成草稿并发布')
    claim_revision(db,s,body.revision,user.id);s.status=body.status;db.commit();return state_view(q,s)


@router.post('/questions/{qid}/clone',status_code=201)
def clone(qid:int,db:Session=Depends(get_db),user:User=Depends(editor)):
    q=get_question(db,qid);s=db.get(QuestionWorkspace,qid)
    content=copy.deepcopy(s.draft if s and s.draft is not None else q.content)
    content['title']=content['title'][:145]+'（副本）'
    new,state=validation(lambda:create_draft(db,user.id,content,previous=q.content));db.commit()
    return state_view(new,state)


@router.get('/questions/{qid}/versions')
def versions(qid:int,db:Session=Depends(get_db),user:User=Depends(editor)):
    q=get_question(db,qid)
    rows=db.query(QuestionRevision).filter_by(question_id=qid).order_by(QuestionRevision.version.desc()).all()
    if not rows and db.get(QuestionWorkspace,qid) is None:
        return [{'version':1,'note':'原题初始版本','created_at':q.created_at,'title':q.content['title']}]
    return [{'version':r.version,'note':r.note,'created_at':r.created_at,'title':r.content['title']} for r in rows]


@router.post('/questions/{qid}/versions/{version}/restore')
def restore(qid:int,version:int,body:RevisionBody,db:Session=Depends(get_db),user:User=Depends(editor)):
    q=get_question(db,qid);s=initialize_workspace(db,q)
    history=db.query(QuestionRevision).filter_by(question_id=qid,version=version).one_or_none()
    if history is None:raise HTTPException(404,'历史版本不存在')
    claim_revision(db,s,body.revision,user.id);s.draft=copy.deepcopy(history.content);db.commit()
    return {**state_view(q,s),'content':s.draft}


def review_query(db,search='',topic=None,question_id=None,class_name='',status='pending',latest_only=True):
    query=db.query(LabAttempt,User).join(User,User.id==LabAttempt.student_id)
    if latest_only:
        latest=db.query(func.max(LabAttempt.id).label('id')).group_by(LabAttempt.question_id,LabAttempt.student_id).subquery()
        query=query.join(latest,LabAttempt.id==latest.c.id)
    if status!='all':query=query.filter(LabAttempt.result['status'].as_string()==('pending_review' if status=='pending' else 'graded'))
    if search:query=query.filter(or_(User.username.contains(search,autoescape=True),User.real_name.contains(search,autoescape=True),User.student_id.contains(search,autoescape=True),LabAttempt.question_snapshot['title'].as_string().contains(search,autoescape=True)))
    if topic:query=query.filter(LabAttempt.question_snapshot['topic'].as_integer()==topic)
    if question_id:query=query.filter(LabAttempt.question_id==question_id)
    if class_name:query=query.filter(User.class_name==class_name)
    return query


def brief_attempt(a,u):
    return {'id':a.id,'question_id':a.question_id,'question_title':a.question_snapshot['title'],
            'topic':a.question_snapshot['topic'],'student_name':u.real_name or u.username,'student_number':u.student_id,
            'class_name':u.class_name,'created_at':a.created_at,'status':a.result['status'],
            'total_score':a.result['total_score'],'total_max':a.result['total_max']}


@router.get('/reviews')
def reviews(search:str=Query('',max_length=150),topic:int|None=Query(None,ge=1,le=9),question_id:int|None=None,
            class_name:str=Query('',max_length=80),status:Literal['pending','graded','all']='pending',latest_only:bool=True,
            page:int=Query(1,ge=1),limit:int=Query(20,ge=1,le=100),db:Session=Depends(get_db),user:User=Depends(grader)):
    query=review_query(db,search,topic,question_id,class_name,status,latest_only)
    count=query.count();rows=query.order_by(LabAttempt.id.asc()).offset((page-1)*limit).limit(limit).all()
    return {'total':count,'items':[brief_attempt(a,u) for a,u in rows]}


@router.get('/reviews/export')
def export(search:str=Query('',max_length=150),topic:int|None=Query(None,ge=1,le=9),question_id:int|None=None,
           class_name:str=Query('',max_length=80),status:Literal['pending','graded','all']='all',latest_only:bool=True,
           db:Session=Depends(get_db),user:User=Depends(grader)):
    def safe(v):
        s='' if v is None else str(v)
        return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r','\n')) else s
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['作答编号','学号','姓名','班级','题目','提交时间','评阅状态','客观得分','人工得分','总分','满分','百分比','评语'])
    for a,u in review_query(db,search,topic,question_id,class_name,status,latest_only).order_by(LabAttempt.id).yield_per(200):
        total=a.result['total_score'];maximum=a.result['total_max']
        writer.writerow([safe(v) for v in [a.id,u.student_id,u.real_name or u.username,u.class_name,a.question_snapshot['title'],a.created_at,
            '已评阅' if a.result['status']=='graded' else '待评阅',a.result['automatic_score'],
            sum(a.review['scores'].values()) if a.review else None,total,maximum,round(total/maximum*100,2) if total is not None and maximum else None,a.review['comment'] if a.review else None]])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="lab-grades.csv"'})


@router.get('/reviews/{attempt_id}')
def review_detail(attempt_id:int,db:Session=Depends(get_db),user:User=Depends(grader)):
    pair=db.query(LabAttempt,User).join(User,User.id==LabAttempt.student_id).filter(LabAttempt.id==attempt_id).one_or_none()
    if pair is None:raise HTTPException(404,'作答不存在或所属用户已删除')
    a,u=pair;draft=db.query(GradeDraft).filter_by(attempt_id=attempt_id,reviewer_id=user.id).one_or_none()
    audit=db.query(GradeAudit,User).join(User,User.id==GradeAudit.reviewer_id).filter(GradeAudit.attempt_id==attempt_id).order_by(GradeAudit.id.desc()).all()
    return {**attempt_view(a),**brief_attempt(a,u),'question':a.question_snapshot,'etag':grade_etag(a),
            'draft':draft.content if draft else None,
            'audit':[{'id':r.id,'reviewer':p.real_name or p.username,'before':r.before,'after':r.after,'reason':r.reason,'created_at':r.created_at} for r,p in audit]}


@router.put('/reviews/{attempt_id}/draft')
def review_draft(attempt_id:int,body:DraftBody,db:Session=Depends(get_db),user:User=Depends(grader)):
    if db.get(LabAttempt,attempt_id) is None:raise HTTPException(404,'作答不存在')
    if len(json.dumps(body.content,ensure_ascii=False))>60000:raise HTTPException(422,'评分草稿过长')
    draft=db.query(GradeDraft).filter_by(attempt_id=attempt_id,reviewer_id=user.id).one_or_none()
    if draft is None:db.add(GradeDraft(attempt_id=attempt_id,reviewer_id=user.id,content=body.content))
    else:draft.content=body.content
    db.commit();return {'saved':True}


@router.post('/reviews/{attempt_id}/grade')
def grade(attempt_id:int,body:ReviewBody,db:Session=Depends(get_db),user:User=Depends(grader)):
    a=db.get(LabAttempt,attempt_id)
    if a is None:raise HTTPException(404,'作答不存在')
    validation(lambda:save_grade(db,a,user.id,body.model_dump(),body.etag,body.reason))
    db.commit();return review_detail(attempt_id,db,user)


@router.get('/snippets')
def snippets(db:Session=Depends(get_db),user:User=Depends(grader)):
    return [{'id':r.id,'text':r.text} for r in db.query(FeedbackSnippet).filter_by(owner_id=user.id).order_by(FeedbackSnippet.id.desc())]


@router.post('/snippets',status_code=201)
def new_snippet(body:SnippetBody,db:Session=Depends(get_db),user:User=Depends(grader)):
    if not body.text.strip():raise HTTPException(422,'评语不能为空')
    if db.query(FeedbackSnippet).filter_by(owner_id=user.id).count()>=100:raise HTTPException(422,'常用评语最多100条')
    value=FeedbackSnippet(owner_id=user.id,text=body.text.strip());db.add(value);db.commit();db.refresh(value)
    return {'id':value.id,'text':value.text}


@router.delete('/snippets/{snippet_id}',status_code=204)
def delete_snippet(snippet_id:int,db:Session=Depends(get_db),user:User=Depends(grader)):
    value=db.query(FeedbackSnippet).filter_by(id=snippet_id,owner_id=user.id).one_or_none()
    if value is None:raise HTTPException(404,'常用评语不存在')
    db.delete(value);db.commit()
