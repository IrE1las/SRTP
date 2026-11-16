"""Launch a self-contained acceptance site without touching the personal DB.

Run from the repository: .runtime/venv/Scripts/python.exe framework/backend/scripts/preview_operation_assessment.py
All generated acceptance data live in .runtime/exam-acceptance; remove after acceptance.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = ROOT / '.runtime' / 'exam-acceptance'
PASSWORD = '00000000'


def prepare(with_ai=False):
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    os.environ['DATABASE_URL'] = 'sqlite:///' + (DIRECTORY / 'acceptance.db').as_posix()
    os.environ['SECRET_KEY'] = secrets.token_urlsafe(40)
    if not with_ai:
        os.environ['DEEPSEEK_API_KEY'] = ''
    os.environ['OPERATION_ASSESSMENT_ENABLED'] = 'true'
    os.environ['EXAM_COMMENTARY_ENABLED'] = 'true'
    sys.path.insert(0, str(ROOT / 'framework' / 'backend'))
    from app.core import config
    config.ENV_FILE = DIRECTORY / 'preview.env'
    from main import app
    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models import User

    def expect(response):
        if response.status_code != 200:
            raise RuntimeError('Acceptance setup failed: ' + response.text)
        return response.json()

    with TestClient(app) as client:
        with SessionLocal() as db:
            exists = db.scalar(select(User).where(User.username == 'exam_demo_teacher'))
            if exists and (DIRECTORY / 'manifest.json').exists():
                return app
            for name, role in [('exam_demo_teacher','teacher'),('exam_demo_student','student')]:
                db.add(User(username=name,password_hash=get_password_hash(PASSWORD),role=role,
                    real_name='评价验收教师' if role=='teacher' else '评价验收学生',
                    student_id='ASSESSMENT-DEMO' if role=='student' else None,
                    class_name='评价验收班' if role=='student' else None))
            db.commit()
        teacher = {'Authorization':'Bearer '+expect(client.post('/api/auth/login',json={'username':'exam_demo_teacher','password':PASSWORD}))['access_token']}
        student = {'Authorization':'Bearer '+expect(client.post('/api/auth/login',json={'username':'exam_demo_student','password':PASSWORD}))['access_token']}
        q = expect(client.post('/api/operations/questions',headers=teacher,json={
            'title':'正常接车进路评价验收','prompt':'使用正常办理方式建立XD至III道接车进路，交卷时保持正确进路与允许信号。',
            'classes':['评价验收班'],'initial':{'interval_available':True,'occupied_sections':[]}}))
        recording = expect(client.post(f"/api/operations/questions/{q['id']}/sessions",headers=teacher,json={'kind':'recording'}))
        for name in ['XDLA','SIIILA']:
            recording=expect(client.post(f"/api/operations/sessions/{recording['session_id']}/events",headers=teacher,json={
                'event_id':str(uuid4()),'sequence':recording['revision']+1,'action':'button','button_id':name}))
        expect(client.post(f"/api/operations/sessions/{recording['session_id']}/stop",headers=teacher))
        expect(client.post(f"/api/operations/sessions/{recording['session_id']}/save-standard",headers=teacher))
        expect(client.put(f"/api/operations/questions/{q['id']}/assessment",headers=teacher,json={
            'revision':0,'enabled':True,'route_ids':['SDM-071'],'confirmed':True}))
        expect(client.post(f"/api/operations/questions/{q['id']}/publish",headers=teacher))
        manifest={'teacher':'exam_demo_teacher','student':'exam_demo_student','question_id':q['id'],'attempts':{}}
        now=datetime.now(timezone.utc)
        for scenario, title in [('normal','正常完成 · 100分'),('clear','误选后清除 · 98分'),
                                ('wrong_locked','错误进路未开放即取消 · 90分'),('wrong_open','错误信号开放后恢复 · 80分'),
                                ('live','手动操作验收')]:
            exam=expect(client.post('/api/exams',headers=teacher,json={'name':title,'version_id':q['version_id'],
                'classes':['评价验收班'],'opens_at':(now-timedelta(minutes=1)).isoformat(),
                'closes_at':(now+timedelta(days=2)).isoformat(),'duration_minutes':120}))
            exam=expect(client.post(f"/api/exams/{exam['id']}/publish",headers=teacher,json={'revision':exam['revision']}))
            if scenario=='live':
                manifest['live_exam_id']=exam['id'];continue
            attempt=expect(client.post(f"/api/exams/{exam['id']}/begin",headers=student,json={'fullscreen':True}))
            sid=attempt['session_id'];sequence=0
            def send(action='button',**values):
                nonlocal sequence
                sequence+=1
                return expect(client.post(f'/api/exams/attempts/{sid}/events',headers=student,json={
                    'event_id':str(uuid4()),'sequence':sequence,'action':action,**values}))
            def wait(seconds):
                time.sleep(seconds)
                return expect(client.post(f'/api/exams/attempts/{sid}/sync',headers=student,json={'fullscreen':True,'events':[]}))
            if scenario=='clear':
                send(button_id='D3DA');send('function',button_id='CLEAR_SELECTION')
            if scenario in {'wrong_locked','wrong_open'}:
                send(button_id='XDLA');send(button_id='S5LA')
                if scenario=='wrong_open':wait(3)
                send('function',button_id='CANCEL_ROUTE');send('target',target_id='XD',target_kind='signal')
                wait(4 if scenario=='wrong_locked' else 1)
            send(button_id='XDLA');send(button_id='SIIILA');wait(3)
            expect(client.post(f'/api/exams/attempts/{sid}/submit',headers=student,json={'expected_sequence':sequence}))
            detail=expect(client.get(f'/api/exams/attempts/{sid}',headers=teacher))
            manifest['attempts'][scenario]={'session_id':sid,'score':detail['automatic_evaluation']['suggested_score']}
        # A separate editable draft lets the user inspect the configuration controls.
        editable=expect(client.post('/api/operations/questions',headers=teacher,json={
            'title':'评价配置验收草稿','prompt':'可在检查发布页查看并选择接车评价模板。','classes':['评价验收班']}))
        manifest['draft_question_id']=editable['id']
        (DIRECTORY/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8016)
    parser.add_argument('--with-ai',action='store_true',help='Use existing AI settings with synthetic feedback only')
    args=parser.parse_args()
    app=prepare(args.with_ai)
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from starlette.exceptions import HTTPException
    dist=ROOT/'framework'/'frontend'/'dist'
    if not (dist/'index.html').exists():
        raise SystemExit('请先在framework/frontend运行npm run build')
    class SpaFiles(StaticFiles):
        async def get_response(self,path,scope):
            try:
                return await super().get_response(path,scope)
            except HTTPException as exc:
                if exc.status_code==404 and '.' not in path.rsplit('/',1)[-1]:
                    return FileResponse(dist/'index.html')
                raise
    app.mount('/',SpaFiles(directory=dist,html=True),name='acceptance-site')
    print(f'Acceptance site: http://127.0.0.1:{args.port}; teacher=exam_demo_teacher; student=exam_demo_student; password={PASSWORD}',flush=True)
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='warning')


if __name__=='__main__':
    main()
