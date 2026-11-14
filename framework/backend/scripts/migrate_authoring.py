"""Create editorial/grade tables and snapshot current published questions."""
import argparse
import copy
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
BACKEND=Path(__file__).resolve().parents[1]
ROOT=BACKEND.parents[1]
sys.path.insert(0,str(BACKEND))
from app.core.database import SessionLocal,engine
from app.models import LabQuestion,QuestionWorkspace,QuestionRevision,GradeDraft,GradeAudit,FeedbackSnippet


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    path=Path(engine.url.database).resolve()
    if engine.url.get_backend_name()!='sqlite' or not path.is_relative_to(ROOT) or not path.is_file():raise ValueError('数据库须是SRTP项目内已有SQLite文件')
    with SessionLocal() as db:count=db.query(LabQuestion).count()
    result={'database':str(path),'existing_questions':count,'applied':False}
    if args.apply:
        backup=ROOT/'outputs/backups'/datetime.now().strftime('authoring-migration-%Y%m%d-%H%M%S-%f')/'railway.db';backup.parent.mkdir(parents=True)
        with sqlite3.connect(path) as source,sqlite3.connect(backup) as target:source.backup(target)
        with engine.begin() as connection:
            for model in [QuestionWorkspace,QuestionRevision,GradeDraft,GradeAudit,FeedbackSnippet]:model.__table__.create(connection,checkfirst=True)
        initialized=0
        with SessionLocal.begin() as db:
            for q in db.query(LabQuestion):
                if db.get(QuestionWorkspace,q.id) is not None:continue
                db.add(QuestionWorkspace(question_id=q.id,status='published',revision=1,published_version=1))
                db.add(QuestionRevision(question_id=q.id,version=1,content=copy.deepcopy(q.content),note='迁移前已发布题目'))
                initialized+=1
        result.update(applied=True,initialized=initialized,backup=str(backup))
        (backup.parent/'migration.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
