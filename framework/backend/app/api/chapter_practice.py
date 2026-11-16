"""Private, per-user random chapter practice."""
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field, StrictBool, StrictStr
from sqlalchemy.orm import Session
from app.api.deps import require_roles
from app.core.database import get_db
from app.services import chapter_practice as service
from app.services import chapter_ai_tutor as tutor

router = APIRouter()
reader = Depends(require_roles('student', 'teacher', 'admin'))


class DrawRequest(BaseModel):
    exclude_ids: list[StrictStr] = Field(default_factory=list, max_length=10000)
    bookmarked_only: StrictBool = False


class SubmitRequest(BaseModel):
    answer: StrictBool | Annotated[StrictStr, Field(max_length=1000)] | Annotated[
        list[Annotated[StrictStr, Field(max_length=1000)]], Field(max_length=20)]


class BookmarkRequest(BaseModel):
    marked: StrictBool


class TutorRequest(BaseModel):
    request_id: UUID
    revision: int = Field(ge=0, strict=True)
    action: Literal['explain', 'ask'] = 'ask'
    message: StrictStr = Field(default='', max_length=1500)

    model_config = {'extra': 'forbid'}


@router.get('/chapters')
def chapters(db: Session = Depends(get_db), user=reader):
    return service.chapters(db, user.id)


@router.post('/chapters/{chapter}/draw')
def draw(body: DrawRequest, chapter: int = Path(ge=1, le=6),
         db: Session = Depends(get_db), user=reader):
    return service.draw(db, user.id, chapter, body.exclude_ids, body.bookmarked_only)


@router.get('/chapters/{chapter}/questions')
def study_questions(chapter: int = Path(ge=1, le=6), db: Session = Depends(get_db), user=reader):
    return service.study_questions(db, user.id, chapter)


@router.post('/questions/{qid}/attempts')
def start_question(qid: str, db: Session = Depends(get_db), user=reader):
    return service.start_question(db, user.id, qid)


@router.get('/attempts/{attempt_id}')
def attempt(attempt_id: str, db: Session = Depends(get_db), user=reader):
    return service.public_attempt(db, service.get_attempt(db, user.id, attempt_id), user.id)


@router.post('/attempts/{attempt_id}/submit')
def submit(attempt_id: str, body: SubmitRequest, db: Session = Depends(get_db), user=reader):
    return service.submit(db, user.id, attempt_id, body.answer)


@router.get('/bookmarks')
def bookmarks(chapter: int | None = Query(None, ge=1, le=6),
              db: Session = Depends(get_db), user=reader):
    return {'items': service.bookmark_ids(db, user.id, chapter)}


@router.get('/attempts/{attempt_id}/ai-chat')
def ai_chat(attempt_id: str, db: Session = Depends(get_db), user=reader):
    return tutor.detail(db, user.id, attempt_id)


@router.post('/attempts/{attempt_id}/ai-chat')
def ask_ai(attempt_id: str, body: TutorRequest, db: Session = Depends(get_db), user=reader):
    return tutor.send(db, user.id, attempt_id, body)


@router.put('/bookmarks/{qid}')
def bookmark(qid: str, body: BookmarkRequest, db: Session = Depends(get_db), user=reader):
    return service.set_bookmark(db, user.id, qid, body.marked)
