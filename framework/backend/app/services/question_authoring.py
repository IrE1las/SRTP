"""Validate editable question content and publish without changing past attempts."""
import copy
import json
import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import update

from app.models import LabQuestion, QuestionWorkspace, QuestionRevision, ShuntingDataset
from app.services.lab_topics import BLUEPRINT, KIND_LABELS, digest
from app.services.shunting_data import DATASET_KEY, STATION_KEY


def topic_catalog():
    return json.loads(BLUEPRINT.read_text(encoding='utf-8'))['topics']+[
        {'id':9,'title':'自主命题','objective':'围绕原图自主编排题目与评分标准。','report':'管理员自编'}]


def text_value(value, name, limit=6000, required=False):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):
        raise ValueError(f'{name}须填写有效文本，最多{limit}字')
    return value.strip()


def strings(value,name,maximum=20,limit=1000):
    if not isinstance(value,list) or len(value)>maximum:
        raise ValueError(f'{name}最多{maximum}项')
    return [text_value(x,name,limit,True) for x in value]


def whole(value,name,low=1,high=100):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f'{name}须为{low}至{high}的整数')
    return value


def validate_content(db, raw, *, publish=False, previous=None):
    if not isinstance(raw,dict): raise ValueError('题目格式不正确')
    topic=whole(raw.get('topic',9),'专题',1,9)
    info=next(t for t in topic_catalog() if t['id']==topic)
    dataset=db.query(ShuntingDataset).filter_by(dataset_key=DATASET_KEY).one_or_none()
    if dataset is None: raise ValueError('缺少原图站场资料')
    result={
        'title':text_value(raw.get('title',''),'题目标题',150,True),
        'prompt':text_value(raw.get('prompt',''),'题干',6000,publish),
        'topic':topic,'topic_info':info,
        'sequence':whole(raw.get('sequence',1),'排序号',1,999),
        'level':text_value(raw.get('level','基础'),'难度',30,True),
        'source_section':text_value(raw.get('source_section','管理员命题'),'命题依据',1500,publish),
        'conditions':strings(raw.get('conditions',[]),'题设条件',15,2000),
        'tags':strings(raw.get('tags',[]),'标签',10,30),
        'devices':strings(raw.get('devices',[]),'关联设备',100,50),
        'diagram_mode':raw.get('diagram_mode','semi_auto' if topic==7 else 'auto' if topic==8 else 'station'),
        'station_key':STATION_KEY,
    }
    if result['diagram_mode'] not in ('station','semi_auto','auto'): raise ValueError('站场展示方式不正确')
    topo=dataset.station_topology
    devices={s['name'] for s in topo['signals']}|{s['id'] for s in topo['switches']}|{s['name'] for s in topo['sections']}
    if set(result['devices'])-devices: raise ValueError('引用了原图未定义的站内设备')
    if publish and result['diagram_mode']!='station' and not result['conditions']:
        raise ValueError('区间题须填写补充题设条件')
    fields=raw.get('fields',[])
    if not isinstance(fields,list) or len(fields)>30 or (publish and not fields):
        raise ValueError('发布题目须有1至30个答题栏')
    result['fields']=[]
    known={f['id']:f for f in (previous or {}).get('fields',[])}
    ids=set()
    for item in fields:
        if not isinstance(item,dict): raise ValueError('答题栏格式不正确')
        fid=item.get('id','')
        if not isinstance(fid,str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,49}',fid) or fid in ids:
            raise ValueError('答题栏编号应唯一，由字母、数字、下划线组成')
        ids.add(fid)
        kind=item.get('kind')
        if kind not in KIND_LABELS: raise ValueError('不支持的题型')
        f={'id':fid,'kind':kind,'label':text_value(item.get('label',''),'答题栏标题',1000,publish),
           'points':whole(item.get('points',10),'答题栏分值')}
        if kind=='essay':
            if 'explanation' in item:
                f['explanation']=text_value(item['explanation'],'参考答案与解析',6000)
            f['criteria']=strings(item.get('criteria',[]),'评分要点',20,1000)
            rubric=item.get('rubric',[])
            if not isinstance(rubric,list) or len(rubric)>15: raise ValueError('分项评分细则最多15项')
            f['rubric']=[]
            rid=set()
            for r in rubric:
                if not isinstance(r,dict): raise ValueError('评分细则格式不正确')
                code=text_value(r.get('id',''),'细则编号',50,True)
                if code in rid: raise ValueError('评分细则编号不能重复')
                rid.add(code)
                f['rubric'].append({'id':code,'label':text_value(r.get('label',''),'细则描述',1000,publish),
                                     'points':whole(r.get('points',1),'细则分值')})
            if publish and f['rubric'] and sum(r['points'] for r in f['rubric'])!=f['points']:
                raise ValueError(f"{f['label']}：细则分值合计须等于本栏分值")
            if publish and not f['criteria'] and not f['rubric']: raise ValueError('论述题须填写评分要点或分项评分细则')
            if not f['criteria'] and f['rubric']: f['criteria']=[r['label'] for r in f['rubric']]
        else:
            f['explanation']=text_value(item.get('explanation',''),'答案解析',6000,publish)
            if kind in ('choice','multi','order'):
                f['options']=strings(item.get('options',[]),'选项',20,1000)
                if len(set(f['options']))!=len(f['options']) or (publish and len(f['options'])<2):
                    raise ValueError('选项不能重复，发布时至少两个选项')
                answer=item.get('expected','' if kind=='choice' else [])
                if kind=='choice':
                    f['expected']=text_value(answer,'参考答案',1000,publish)
                    if publish and answer not in f['options']: raise ValueError('正确答案须在选项中')
                else:
                    f['expected']=strings(answer,'参考答案',20,1000)
                    if len(set(f['expected']))!=len(f['expected']): raise ValueError('答案不能重复')
                    if publish and (not f['expected'] or set(f['expected'])-set(f['options'])): raise ValueError('请选择有效答案')
                    if publish and kind=='order' and set(f['expected'])!=set(f['options']): raise ValueError('排序答案须含全部选项')
                if kind=='multi':
                    f['scoring']=item.get('scoring','exact')
                    if f['scoring'] not in ('exact','partial'): raise ValueError('多选评分方式不正确')
            elif kind=='cell':
                f['expected']=text_value(item.get('expected',''),'参考填写',6000,publish)
                f['accepted_answers']=strings(item.get('accepted_answers',[]),'可接受答案',10,6000)
                f['matching']=item.get('matching','ordered' if item.get('binding',{}).get('column')=='排列进路按下按钮' else 'tokens')
                if f['matching'] not in ('tokens','ordered','text'): raise ValueError('填写项比对方式不正确')
                origin=known.get(fid,{})
                # Only retain original provenance when the answer and match policy are unchanged.
                expected_matching=origin.get('matching','ordered' if origin.get('binding',{}).get('column')=='排列进路按下按钮' else 'tokens')
                if (origin.get('expected')==f['expected'] and f['matching']==expected_matching
                    and not f['accepted_answers']):
                    for key in ['binding','expected_runs']:
                        if key in origin:f[key]=copy.deepcopy(origin[key])
        result['fields'].append(f)
    if previous and 'evidence' in previous:result['evidence']=copy.deepcopy(previous['evidence'])
    result['authoring_source']='administrator'
    return dataset,result


def state_view(q, state):
    draft=state.draft if state else None
    shown=draft or q.content
    return {'id':q.id,'key':q.key,'title':shown['title'],'topic':shown['topic'],
            'topic_title':shown['topic_info']['title'],'status':state.status if state else 'published',
            'has_draft':draft is not None,'revision':state.revision if state else 0,
            'published_version':state.published_version if state else 1,
            'updated_at':state.updated_at if state else q.created_at,
            'field_count':len(shown['fields']),'total_points':sum(f['points'] for f in shown['fields']),
            'tags':shown.get('tags',[])}


def get_question(db,qid):
    q=db.get(LabQuestion,qid)
    if q is None:raise HTTPException(404,'题目不存在')
    return q


def initialize_workspace(db,q):
    state=db.get(QuestionWorkspace,q.id)
    if state is None:
        state=QuestionWorkspace(question_id=q.id,status='published',revision=0,published_version=1)
        db.add(state)
        db.add(QuestionRevision(question_id=q.id,version=1,content=copy.deepcopy(q.content),note='原题初始版本'))
        db.flush()
    return state


def claim_revision(db,state,revision,user_id):
    if revision!=state.revision:raise HTTPException(409,'题目已在其他窗口更新，请重新加载后编辑')
    changed=db.execute(update(QuestionWorkspace).where(QuestionWorkspace.question_id==state.question_id,
            QuestionWorkspace.revision==revision).values(revision=revision+1,updated_by=user_id,updated_at=datetime.now(timezone.utc).replace(tzinfo=None)),
            execution_options={'synchronize_session':False})
    if changed.rowcount!=1:raise HTTPException(409,'题目编辑冲突，请重新加载')
    db.refresh(state)


def create_draft(db,user_id,raw,previous=None):
    dataset,item=validate_content(db,raw,previous=previous)
    key='custom-'+uuid.uuid4().hex[:16]
    item['key']=key
    q=LabQuestion(key=key,dataset_id=dataset.id,topic=item['topic'],sequence=item['sequence'],content=item,fingerprint=digest(item))
    db.add(q);db.flush()
    state=QuestionWorkspace(question_id=q.id,status='draft',draft=item,revision=1,published_version=0,updated_by=user_id)
    db.add(state);db.flush()
    return q,state
