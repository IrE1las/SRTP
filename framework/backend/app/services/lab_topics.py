"""Finite report-authored questions; table answers are bound to original sources."""
import copy
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.lab_topic import LabAttempt, LabQuestion
from app.models.shunting_route import ShuntingDataset, ShuntingRoute
from app.services.shunting_data import DATASET_KEY, STATION_KEY
from app.services.answer_references import load_references, explanation_text

ROOT = Path(__file__).resolve().parents[4]
BLUEPRINT = ROOT / 'ai_design/station/report_topic_blueprint.json'
KIND_LABELS = {'choice':'判断选择','multi':'多项辨析','order':'时序排序','cell':'联锁表填写','essay':'记录与分析'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def resolve_blueprint(db: Session):
    blueprint = json.loads(BLUEPRINT.read_text(encoding='utf-8'))
    if blueprint['schema_version'] != 1 or blueprint['station_key'] != STATION_KEY:
        raise ValueError('专题版本或原图站场关联不正确')
    dataset = db.query(ShuntingDataset).filter_by(dataset_key=DATASET_KEY).one_or_none()
    if dataset is None or not dataset.source.get('reviewed'):
        raise ValueError('请先导入经人工核对的原图调车联锁表')
    for report in blueprint['reports']:
        path = (ROOT/report['source']).resolve()
        if not path.is_relative_to(ROOT/'车站与区间控制实验') or not path.is_file():
            raise ValueError('实验报告来源不在指定目录')
        if hashlib.sha256(path.read_bytes()).hexdigest() != report['sha256'].lower():
            raise ValueError('实验报告已变化，需先复核题目依据')
    train_path = ROOT/'ai_design/station/interlocking_table.csv'
    data = train_path.read_bytes()
    try:
        train_text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        train_text = data.decode('gb18030')
    trains = {int(r['进路号码']):r for r in csv.DictReader(io.StringIO(train_text))}
    shunting = {r.route_number:r for r in db.query(ShuntingRoute).filter_by(dataset_id=dataset.id)}
    topology = dataset.station_topology
    inventory = ({s['name'] for s in topology['signals']} | {s['id'] for s in topology['switches']}
                 | {s['name'] for s in topology['sections']})
    topics = {t['id']:t for t in blueprint['topics']}
    if set(topics) != set(range(1,9)) or len(blueprint['questions']) != 24:
        raise ValueError('专题应完整覆盖八个实验的24道复合题')
    keys = set()
    resolved = []
    references = load_references(ROOT)
    manual_keys = {(q['key'], f['id']) for q in blueprint['questions'] for f in q['fields'] if f['kind']=='essay'}
    if set(references) != manual_keys:
        raise ValueError('参考解答与实验专题答题栏不一致')
    for source in blueprint['questions']:
        item = copy.deepcopy(source)
        if item['key'] in keys or item['topic'] not in topics or set(item['devices']) - inventory:
            raise ValueError('题目编号重复或引用原图以外的设备')
        keys.add(item['key'])
        item['topic_info'] = topics[item['topic']]
        item['evidence'] = {'dataset_sha256':dataset.content_sha256,
                            'train_table_sha256':hashlib.sha256(data).hexdigest(),
                            'station_key':STATION_KEY}
        ids = set()
        for field in item['fields']:
            if field['id'] in ids or field['kind'] not in KIND_LABELS or field['points'] <= 0:
                raise ValueError('答题栏定义不正确')
            ids.add(field['id'])
            if field['kind'] == 'cell':
                b = field['binding']
                if b['table'] == 'shunting':
                    route = shunting[b['route_number']]
                    field['expected'] = route.fields[b['column']] or ''
                    field['expected_runs'] = route.rich_text.get(b['column'], [])
                elif b['table'] == 'train':
                    field['expected'] = trains[b['route_number']][b['column']]
                else:
                    raise ValueError('未知联锁表来源')
            if field['kind'] == 'essay':
                if not field.get('criteria') or 'expected' in field:
                    raise ValueError('论述题必须有教师评阅要点，不能伪设唯一答案')
                field['explanation'] = explanation_text(references[(item['key'], field['id'])])
            elif 'expected' not in field or not field.get('explanation'):
                raise ValueError('客观题缺少答案或原因解释')
            if field['kind'] in ('multi','order') and set(field['expected']) - set(field['options']):
                raise ValueError('答案不在给定选项中')
            if field['kind'] == 'choice' and field['expected'] not in field['options']:
                raise ValueError('答案不在给定选项中')
        resolved.append(item)
    return dataset, resolved


def import_topics(db: Session):
    dataset, items = resolve_blueprint(db)
    inserted = updated = 0
    for item in items:
        fingerprint = digest(item)
        existing = db.query(LabQuestion).filter_by(key=item['key']).one_or_none()
        if existing is None:
            db.add(LabQuestion(key=item['key'],dataset_id=dataset.id,topic=item['topic'],sequence=item['sequence'],content=item,fingerprint=fingerprint))
            inserted += 1
        elif existing.fingerprint != fingerprint:
            if existing.content.get('authoring_source')=='administrator':
                raise ValueError('题目已由管理员网页编辑，不能被原始导入脚本覆盖')
            if db.query(LabAttempt).filter_by(question_id=existing.id).first():
                raise ValueError('已有作答的题目不可覆盖，请建立新版本')
            existing.content = item
            existing.fingerprint = fingerprint
            updated += 1
    db.flush()
    return {'topics':8,'total':len(items),'inserted':inserted,'updated':updated}


def public_question(question, detail=True):
    item = question.content
    result = {k:item[k] for k in ['key','topic','sequence','title','level','topic_info']}
    result.update({'id':question.id,'kinds':list(dict.fromkeys(KIND_LABELS[f['kind']] for f in item['fields'])),
                   'automatic_max':sum(f['points'] for f in item['fields'] if f['kind'] != 'essay'),
                   'manual_max':sum(f['points'] for f in item['fields'] if f['kind'] == 'essay')})
    if detail:
        result.update({k:item[k] for k in ['prompt','conditions','source_section','devices','station_key']})
        result['fingerprint'] = question.fingerprint
        result['diagram_mode'] = item.get('diagram_mode','semi_auto' if item['topic']==7 else 'auto' if item['topic']==8 else 'station')
        result['fields'] = [{k:f[k] for k in ['id','label','kind','points','options'] if k in f} for f in item['fields']]
    return result


def normalize_cell(value):
    value = str(value).translate(str.maketrans('（）［］｛｝＜＞，；','()[]{}<>,;'))
    value = value.translate(str.maketrans({'Ⅰ':'I','Ⅱ':'II','Ⅲ':'III','Ⅳ':'IV','₀':'0','₁':'1','₂':'2','₃':'3','₄':'4','₅':'5','₆':'6','₇':'7','₈':'8','₉':'9'}))
    return re.sub(r'\s+', '', value).replace('、',',')


def evaluate(content, answers):
    fields = {f['id']:f for f in content['fields']}
    if set(answers) != set(fields):
        raise ValueError('请完成本题全部答题栏；答案不能包含题目之外的字段')
    feedback = []
    auto_score = auto_max = manual_max = 0
    for fid, field in fields.items():
        value, kind = answers[fid], field['kind']
        if kind in ('multi','order'):
            if (not isinstance(value,list) or not value or any(not isinstance(x,str) for x in value)
                    or len(set(value)) != len(value) or set(value) - set(field['options'])):
                raise ValueError('选择或排序答案包含无效/重复选项')
            if kind == 'order' and set(value) != set(field['options']):
                raise ValueError('排序题须包含全部事件')
        elif not isinstance(value,str) or not value.strip() or len(value) > 6000:
            raise ValueError('请填写非空文本，且每项不超过6000字')
        if kind == 'choice' and value not in field['options']:
            raise ValueError('答案不在本题选项中')
        if kind == 'essay':
            manual_max += field['points']
            feedback.append({'id':fid,'label':field['label'],'status':'pending_review','max_points':field['points'],
                             'criteria':field['criteria'],'rubric':field.get('rubric',[]),'message':'已保存，等待教师结合实验记录和论证评阅。'})
            if field.get('explanation'):
                feedback[-1]['explanation'] = field['explanation']
            continue
        expected = field['expected']
        errors = []
        if kind == 'cell':
            # Condition prefixes remain attached to their original device token;
            # bracket types/positions are never discarded during comparison.
            actual_parts = Counter(filter(None,normalize_cell(value).split(',')))
            expected_parts = Counter(filter(None,normalize_cell(expected).split(',')))
            correct = actual_parts == expected_parts
            missing = list((expected_parts-actual_parts).elements())
            extra = list((actual_parts-expected_parts).elements())
            if missing: errors.append('漏填或记号不符：'+'、'.join(missing))
            if extra: errors.append('多填或记号不符：'+'、'.join(extra))
            match_mode=field.get('matching','ordered' if field.get('binding',{}).get('column')=='排列进路按下按钮' else 'tokens')
            if correct and match_mode == 'ordered':
                correct = normalize_cell(value) == normalize_cell(expected)
                if not correct: errors.append('始端与终端按钮的排列顺序不正确')
            if match_mode=='text':
                correct=str(value).strip()==str(expected).strip()
                errors=[] if correct else ['填写内容与参考答案不一致']
            for alternative in field.get('accepted_answers',[]):
                if match_mode=='text':accepted=str(value).strip()==alternative.strip()
                elif match_mode=='ordered':accepted=normalize_cell(value)==normalize_cell(alternative)
                else:accepted=actual_parts==Counter(filter(None,normalize_cell(alternative).split(',')))
                if accepted:correct=True;errors=[];break
        elif kind == 'multi':
            correct = set(value) == set(expected)
            errors = ['漏选：'+'、'.join(x for x in expected if x not in value)] if set(expected)-set(value) else []
            if set(value)-set(expected): errors.append('多选：'+'、'.join(x for x in value if x not in expected))
        else:
            correct = value == expected
            if not correct: errors.append('事件顺序不正确' if kind == 'order' else '判断不正确')
        points = field['points'] if correct else 0
        if kind=='multi' and field.get('scoring')=='partial' and not set(value)-set(expected):
            points=round(field['points']*len(set(value)&set(expected))/len(expected),2)
        auto_score += points
        auto_max += field['points']
        feedback.append({'id':fid,'label':field['label'],'status':'correct' if correct else 'partial' if points else 'incorrect',
                         'points':points,'max_points':field['points'],'errors':errors,'expected':expected,
                         'expected_runs':field.get('expected_runs',[]),'explanation':field['explanation']})
    return {'status':'pending_review' if manual_max else 'graded','automatic_score':auto_score,
            'automatic_max':auto_max,'manual_max':manual_max,'total_score':None if manual_max else auto_score,
            'total_max':auto_max+manual_max,'feedback':feedback}


def attempt_view(attempt):
    return {'id':attempt.id,'question_id':attempt.question_id,'student_id':attempt.student_id,
            'question_title':attempt.question_snapshot['title'], 'topic':attempt.question_snapshot['topic'],
            'answers':attempt.answers,'result':attempt.result,'review':attempt.review,
            'created_at':attempt.created_at,'reviewed_at':attempt.reviewed_at}
