"""Read-only six-chapter directory; reference answers require teacher access."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.chapter_bank import ChapterBankQuestion
from app.services import chapter_bank as service
from app.api.chapter_practice import router as practice_router

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
    if row is None:
        raise HTTPException(404, '题目不存在')
    return row.content
