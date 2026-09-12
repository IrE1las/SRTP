"""Application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ai_scores, auth, exercise_runtime, exercises, interlocking, interlocking_exam, settings, statistics
from app.api import shunting_data, shunting_questions
from app.api import lab_topics
from app.api import management
from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.services.interlocking.seed_service import seed_default_station
import app.models  # noqa: F401 - imported so metadata includes all ORM tables

app = FastAPI(
    title="铁路计算机联锁仿真实训系统 API",
    description="B/S 架构铁路联锁仿真实训系统后端接口",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


DEFAULT_ADMIN_PASSWORD = '00000000'  # 团队约定的共享本机管理员口令，仅用于本地空数据库初始化


def _ensure_default_admin() -> None:
    """Create the shared admin account when the local database has no administrator."""

    with SessionLocal() as db:
        if db.query(User).filter(User.role == 'admin').first() is not None:
            return
        db.add(User(
            username='admin',
            password_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            real_name='管理员',
            role='admin',
            student_id='',
            class_name='',
        ))
        db.commit()


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables and seed the local default admin and demo station."""

    Base.metadata.create_all(bind=engine)
    _ensure_default_admin()
    with SessionLocal() as db:
        seed_default_station(db)


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return backend health status."""

    return {"status": "ok", "service": "railway-interlocking-api"}


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(interlocking.router, prefix="/api/interlocking", tags=["interlocking"])
app.include_router(exercises.router, prefix="/api", tags=["exercises"])
app.include_router(exercise_runtime.router, prefix="/api/exercise-runtime", tags=["exercise-runtime"])
app.include_router(ai_scores.router, prefix="/api/ai-scores", tags=["ai-scores"])
app.include_router(statistics.router, prefix="/api/statistics", tags=["statistics"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(interlocking_exam.router, prefix="/api", tags=["interlocking-exam"])
app.include_router(shunting_data.router, prefix="/api/exam/shunting", tags=["shunting-data"])
app.include_router(shunting_questions.router, prefix="/api/exam/shunting", tags=["shunting-questions"])
app.include_router(lab_topics.router, prefix="/api/lab-topics", tags=["lab-topics"])
app.include_router(management.router, prefix="/api/management", tags=["management"])
