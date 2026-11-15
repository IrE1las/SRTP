"""Student question pool for the reviewed original-station shunting routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.shunting_route import ShuntingQuestion, ShuntingRoute
from app.schemas.shunting import ShuntingAnswerSubmission
from app.services.shunting_questions import (
    answer_key,
    evaluate_answer,
    generate_shunting_questions,
    get_dataset,
    public_question,
)

router = APIRouter()


def _question(db: Session, question_id: int) -> tuple[ShuntingQuestion, ShuntingRoute]:
    try:
        dataset = get_dataset(db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    question = (
        db.query(ShuntingQuestion)
        .filter_by(id=question_id, dataset_id=dataset.id)
        .one_or_none()
    )
    if question is None:
        raise HTTPException(status_code=404, detail="调车进路题目不存在")
    route = db.query(ShuntingRoute).filter_by(id=question.route_id, dataset_id=dataset.id).one_or_none()
    if route is None:
        raise HTTPException(status_code=500, detail="题目关联的原始进路数据不存在")
    return question, route


@router.post('/questions/generate')
def generate_questions(
    db: Session = Depends(get_db),
    _current_user: Any = Depends(require_roles('teacher', 'admin')),
) -> dict[str, int]:
    """Generate or refresh the deterministic 35-question source-backed pool."""

    try:
        result = generate_shunting_questions(db)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise


@router.get('/questions')
def list_questions(
    db: Session = Depends(get_db),
    _current_user: Any = Depends(require_roles('student', 'teacher', 'admin')),
) -> list[dict[str, Any]]:
    """List public question metadata; answer specifications are excluded."""

    try:
        dataset = get_dataset(db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pairs = (
        db.query(ShuntingQuestion, ShuntingRoute)
        .join(ShuntingRoute, ShuntingRoute.id == ShuntingQuestion.route_id)
        .filter(ShuntingQuestion.dataset_id == dataset.id, ShuntingQuestion.is_active.is_(True))
        .order_by(ShuntingRoute.route_number)
        .all()
    )
    return [public_question(question, route) for question, route in pairs]


@router.get('/questions/{question_id}/answer')
def question_answer_key(
    question_id: int,
    db: Session = Depends(get_db),
    _current_user: Any = Depends(require_roles('teacher', 'admin')),
) -> dict[str, Any]:
    question, route = _question(db, question_id)
    return answer_key(question, route)


@router.post('/questions/{question_id}/submit')
def submit_question_answer(
    question_id: int,
    answer: ShuntingAnswerSubmission,
    db: Session = Depends(get_db),
    _current_user: Any = Depends(require_roles('student', 'teacher', 'admin')),
) -> dict[str, Any]:
    question, _route = _question(db, question_id)
    if not question.is_active:
        raise HTTPException(status_code=404, detail="调车进路题目已停用")
    result = evaluate_answer(question, answer.model_dump())
    result.update({"question_id": question.id, "route_number": question.source_snapshot["route_number"]})
    return result


@router.get('/questions/{question_id}')
def question_detail(
    question_id: int,
    db: Session = Depends(get_db),
    _current_user: Any = Depends(require_roles('student', 'teacher', 'admin')),
) -> dict[str, Any]:
    question, route = _question(db, question_id)
    if not question.is_active:
        raise HTTPException(status_code=404, detail="调车进路题目已停用")
    return public_question(question, route)
