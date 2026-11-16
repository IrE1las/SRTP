"""Read-only six-chapter directory; reference answers require teacher access."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.chapter_bank import ChapterBankQuestion
from app.services import chapter_bank as service
from app.api.chapter_practice import router as practice_router
from app.services import chapter_authoring as authoring
from app.schemas.chapter_authoring import ChapterDraft, ChapterEdit
from app.services.chapter_practice import effective_rule, load_rules, valid_rule

router = APIRouter()
router.include_router(practice_router, prefix='/practice')
reader = Depends(require_roles('student', 'teacher', 'admin'))
reviewer = Depends(require_roles('teacher', 'admin'))


@router.get('/chapters')
def chapters(db: Session = Depends(get_db), user=reader):
    return service.chapters(db)


@router.get('/chapters/{chapter}/questions')
def questions(chapter: int = Path(ge=1, le=6), page: int = Query(1, ge=1),
              limit: int = Query(30, ge=1, le=100), search: str = Query('', max_length=150),
              kind: Literal['all','objective','essay','choice','multi','true_false','cell'] = 'objective',
              status: Literal['all','pending','answered'] = 'all',
              db: Session = Depends(get_db), user=reader):
    return service.question_list(db, chapter, page=page, limit=limit, search=search, kind=kind, status=status)


@router.get('/questions/{qid}/reference')
def reference(qid: str, db: Session = Depends(get_db), user=reviewer):
    row = db.get(ChapterBankQuestion, qid)
    if row is None or not valid_rule(row, effective_rule(row, load_rules())):
        raise HTTPException(404, '题目不存在')
    return row.content


@router.get('/questions')
def all_questions(chapter: int | None = Query(None, ge=1, le=6), page: int = Query(1, ge=1),
                  limit: int = Query(20, ge=1, le=100), search: str = Query('', max_length=150),
                  kind: Literal['objective','choice','multi','true_false','cell'] = 'objective',
                  progress: Literal['all','correct','not_correct','unanswered'] = 'all',
                  db: Session = Depends(get_db), user=reader):
    return service.question_list(db, chapter, page=page, limit=limit, search=search,
                                 kind=kind, user_id=user.id, progress=progress)


@router.get('/manage/questions')
def managed_questions(chapter: int | None = Query(None, ge=1, le=6), page: int = Query(1, ge=1),
                      limit: int = Query(20, ge=1, le=100), search: str = Query('', max_length=150),
                      kind: Literal['objective','choice','multi','true_false','cell'] = 'objective',
                      db: Session = Depends(get_db), user=reviewer):
    return authoring.listing(db, chapter=chapter, page=page, limit=limit, search=search, kind=kind)


@router.post('/manage/questions', status_code=201)
def create_question(body: ChapterDraft, db: Session = Depends(get_db), user=reviewer):
    return authoring.create(db, user, body)


@router.get('/manage/questions/{qid}')
def managed_question(qid: str, db: Session = Depends(get_db), user=reviewer):
    return authoring.detail(authoring.find(db, qid))


@router.put('/manage/questions/{qid}')
def edit_question(qid: str, body: ChapterEdit, db: Session = Depends(get_db), user=reviewer):
    return authoring.edit(db, user, qid, body)


@router.delete('/manage/questions/{qid}')
def delete_question(qid: str, revision: int = Query(ge=0), db: Session = Depends(get_db), user=reviewer):
    return authoring.remove(db, user, qid, revision)
