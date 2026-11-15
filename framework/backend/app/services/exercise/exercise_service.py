"""Exercise CRUD and query service."""

from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.station import Station
from app.schemas.exercise import ExerciseCreateRequest, ExerciseUpdateRequest
from app.services.interlocking.seed_service import seed_default_station


def ensure_station_id(db: Session, station_id: int | None) -> int:
    """Return the given station ID or seed and return the default station ID."""

    if station_id is not None:
        return station_id
    return seed_default_station(db).id


def create_exercise(db: Session, teacher_id: int, payload: ExerciseCreateRequest) -> Exercise:
    """Create a teacher exercise."""

    station_id = ensure_station_id(db, payload.station_id)
    exercise = Exercise(
        teacher_id=teacher_id,
        station_id=station_id,
        title=payload.title,
        description=payload.description,
        exercise_type=payload.exercise_type,
        target_routes=[route.model_dump() for route in payload.target_routes],
        time_limit=payload.time_limit,
        difficulty=payload.difficulty,
        scoring_rules=payload.scoring_rules,
        is_active=payload.is_active,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


def list_teacher_exercises(db: Session, teacher_id: int | None) -> list[Exercise]:
    """Return exercises created by a teacher."""

    query = db.query(Exercise)
    if teacher_id is not None:
        query = query.filter(Exercise.teacher_id == teacher_id)
    return query.order_by(Exercise.created_at.desc(), Exercise.id.desc()).all()


def list_lobby_exercises(db: Session) -> list[Exercise]:
    """Return active exercises for the student lobby."""

    return (
        db.query(Exercise)
        .filter(Exercise.is_active.is_(True))
        .order_by(Exercise.created_at.desc(), Exercise.id.desc())
        .all()
    )


def get_exercise(db: Session, exercise_id: int) -> Exercise | None:
    """Return an exercise by ID."""

    return db.get(Exercise, exercise_id)


def update_exercise(db: Session, exercise: Exercise, payload: ExerciseUpdateRequest) -> Exercise:
    """Update an exercise."""

    update_data = payload.model_dump(exclude_unset=True)
    if "target_routes" in update_data and update_data["target_routes"] is not None:
        update_data["target_routes"] = [
            route.model_dump() if hasattr(route, "model_dump") else route
            for route in payload.target_routes or []
        ]
    for key, value in update_data.items():
        setattr(exercise, key, value)
    db.commit()
    db.refresh(exercise)
    return exercise


def delete_exercise(db: Session, exercise: Exercise) -> None:
    """Delete an exercise."""

    db.delete(exercise)
    db.commit()


def get_station(db: Session, station_id: int) -> Station | None:
    """Return a station by ID."""

    return db.get(Station, station_id)
