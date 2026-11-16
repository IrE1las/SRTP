"""Isolated capacity/concurrency probe. Prints aggregate metrics, never personal data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import platform
import secrets
import statistics
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',default=str(ROOT/'.runtime'/'tmp'/'exam-assessment-benchmark'))
    parser.add_argument('--rounds',type=int,default=10)
    parser.add_argument('--skip-capacity',action='store_true')
    parser.add_argument('--mixed',action='store_true',help='Add 20 clear-selection clicks per 100 syncs')
    parser.add_argument('--stagger',action='store_true',help='Spread the students uniformly over each second')
    args=parser.parse_args()
    directory=Path(args.directory).resolve()
    if not directory.is_relative_to(ROOT) or (directory/'capacity.db').exists():
        raise SystemExit('Use a new directory inside this project; existing benchmark data are not overwritten.')
    directory.mkdir(parents=True,exist_ok=True)
    os.environ.update(DATABASE_URL='sqlite:///'+(directory/'capacity.db').as_posix(),
                      SECRET_KEY=secrets.token_urlsafe(40),DEEPSEEK_API_KEY='')
    sys.path.insert(0,str(ROOT/'framework'/'backend'))
    from app.core import config
    config.ENV_FILE=directory/'preview.env'
    from app.core.database import Base,engine,SessionLocal
    from app.core.security import create_access_token
    from app.models import User
    from app.models.operation import OperationQuestion,OperationVersion,OperationSession,OperationEvent
    from app.models.operation_assessment import OperationAssessmentConfig,OperationEvidenceEvent
    from app.models.exam import Exam,ExamParticipant
    from app.schemas.operation import Click
    from app.services import exams,operations as ops
    from app.services.operation_assessment import configuration,archive
    from app.services.simulation_console import clock
    from sqlalchemy import select,func
    Base.metadata.create_all(engine)
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as db:
        teacher=User(username='capacity_teacher',password_hash='unused',role='teacher',real_name='合成教师')
        db.add(teacher);db.flush()
        q=OperationQuestion(owner_id=teacher.id);db.add(q);db.flush()
        version=OperationVersion(question_id=q.id,number=1,status='published',title='合成接车',prompt='正常办理指定接车进路。',
            classes=['合成班'],initial={'interval_available':True,'occupied_sections':[]},station_version=ops.station_version(),
            standard_log=[{'action':'button','button_id':b,'result':{'accepted':True}} for b in ['XDLA','SIIILA']])
        db.add(version);db.flush()
        db.add(OperationAssessmentConfig(version_id=version.id,content={'enabled':True,'route_ids':['SDM-071'],
            'confirmed':True,'wrong_signal_cap':False,'rubric_version':configuration.RUBRIC_VERSION,'schema_version':1}))
        db.flush()
        with clock.at(now):
            frozen={**ops.detail(q,version),'assessment':configuration.freeze(db,version,version.initial)}
        exam=Exam(owner_id=teacher.id,name='容量验证',status='published',revision=2,version_id=version.id,
            classes=['合成班'],opens_at=now-timedelta(minutes=1),closes_at=now+timedelta(days=1),duration_minutes=120,
            question_snapshot=frozen)
        db.add(exam);db.flush()
        students=[]
        for i in range(102):
            student=User(username='capacity_'+str(i),password_hash='unused',role='student',real_name='合成学生',
                         student_id='capacity_'+str(i),class_name='合成班')
            db.add(student);db.flush()
            db.add(ExamParticipant(exam_id=exam.id,student_id=student.id,identity_snapshot={
                'real_name':'合成学生','student_id':student.student_id,'class_name':'合成班'}))
            students.append(student.id)
        eid=exam.id;db.commit()
    report={'environment':{'python':platform.python_version(),'platform':platform.system(),
            'logical_cpus':os.cpu_count(),'transport':'in-process FastAPI TestClient; no real network'},'capacity':[]}
    for index,count in enumerate([] if args.skip_capacity else [500,2000]):
        with SessionLocal() as db, ops.LOCK,exams.atomic(db),clock.at(now):
            student=db.get(User,students[index]);attempt=exams.begin(db,student,eid,True);sid=attempt['session_id']
        started=time.perf_counter()
        for sequence in range(1,count+1):
            values={'action':'function','button_id':'CLEAR_SELECTION'} if sequence<=count-2 else {
                'action':'button','button_id':'XDLA' if sequence==count-1 else 'SIIILA'}
            with SessionLocal() as db,ops.LOCK,exams.atomic(db),clock.at(now):
                exams.click(db,db.get(User,students[index]),sid,Click(event_id=uuid4(),sequence=sequence,**values),light=True)
        with SessionLocal() as db,ops.LOCK,exams.atomic(db),clock.at(now+timedelta(seconds=3)):
            student=db.get(User,students[index]);attempt=exams.owned(db,student,sid)
            result=exams.detail(db,student,attempt,refresh=True,after_sequence=count)
            state_version=result['console']['state_version']
            light=exams.detail(db,student,attempt,refresh=True,after_sequence=count,state_version=state_version)
            logical=exams.submit(db,student,sid,count)
            from app.services.operation_assessment.service import view
            evaluation=view(db,sid)
            clicks=db.scalar(select(func.sum(func.length(OperationEvent.content))).where(OperationEvent.session_id==sid))
            business=db.scalar(select(func.sum(func.length(OperationEvidenceEvent.content))).where(OperationEvidenceEvent.session_id==sid))
            state=db.get(OperationSession,sid).engine_state
            events=db.scalar(select(func.count()).select_from(OperationEvidenceEvent).where(OperationEvidenceEvent.session_id==sid))
            report['capacity'].append({'click_count':count,'business_batches':events,'click_json_characters':clicks,
                'business_json_characters':business,'current_state_utf8_bytes':len(json.dumps(state,ensure_ascii=False).encode()),
                'unchanged_response_utf8_bytes':len(json.dumps(light,ensure_ascii=False,separators=(',',':')).encode()),
                'score':evaluation['suggested_score'],'elapsed_seconds':round(time.perf_counter()-started,3)})
    # Give each concurrent student a distinct initialized session and signed synthetic identity.
    clients=[]
    for uid in students[2:]:
        with SessionLocal() as db,ops.LOCK,exams.atomic(db),clock.at(now):
            student=db.get(User,uid);attempt=exams.begin(db,student,eid,True)
            token=create_access_token({'sub':str(uid),'username':student.username,'role':'student','ver':student.token_version})
            clients.append({'sid':attempt['session_id'],'token':token,'version':attempt['console']['snapshot']['version']})
    from fastapi.testclient import TestClient
    from main import app
    latencies=[];sizes=[];errors=[];click_latencies=[]
    with TestClient(app) as client,ThreadPoolExecutor(max_workers=100) as pool:
        def sync(pair):
            index,item=pair
            if args.stagger:
                delay=start+index/100-time.perf_counter()
                if delay>0:
                    time.sleep(delay)
            if args.mixed and index%5==round_number%5:
                click_start=time.perf_counter()
                response=client.post('/api/exams/attempts/'+item['sid']+'/events?light=true',
                    headers={'Authorization':'Bearer '+item['token']},json={'event_id':str(uuid4()),
                    'sequence':item.get('sequence',0)+1,'action':'function','button_id':'CLEAR_SELECTION'})
                click_latency=(time.perf_counter()-click_start)*1000
                if response.status_code==200:
                    item['sequence']=response.json()['revision'];item['version']=response.json()['state_version']
                else:
                    errors.append(response.status_code)
                click_latencies.append(click_latency)
            started=time.perf_counter()
            response=client.post('/api/exams/attempts/'+item['sid']+'/sync',headers={'Authorization':'Bearer '+item['token']},
                json={'fullscreen':True,'events':[],'after_sequence':item.get('sequence',0),'state_version':item['version']})
            return (time.perf_counter()-started)*1000,len(response.content),response.status_code
        for round_number in range(args.rounds):
            start=time.perf_counter()
            for latency,size,status in pool.map(sync,enumerate(clients)):
                latencies.append(latency);sizes.append(size)
                if status!=200:errors.append(status)
            remaining=1-(time.perf_counter()-start)
            if remaining>0:time.sleep(remaining)
    values=sorted(latencies)
    report['concurrency']={'students':100,'rounds':args.rounds,'requests':len(values),'errors':errors,
        'pattern':'100 simultaneous unchanged sync requests each round, at least 1 second between round starts',
        'p50_ms':round(statistics.median(values),2),'p95_ms':round(values[int((len(values)-1)*.95)],2),
        'max_ms':round(max(values),2),'max_response_bytes':max(sizes)}
    if click_latencies:
        ordered=sorted(click_latencies)
        report['concurrency']['click_requests']=len(ordered)
        report['concurrency']['click_p95_ms']=round(ordered[int((len(ordered)-1)*.95)],2)
        report['concurrency']['pattern']='100 syncs + 20 business clicks per round, starts at least one second apart'
    report['concurrency']['staggered_arrivals']=args.stagger
    engine.dispose()
    (directory/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
