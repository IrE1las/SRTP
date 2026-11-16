"""Application entry point."""

import asyncio
import logging
from pathlib import Path
import tempfile
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ai_scores, auth, exercise_runtime, exercises, interlocking, settings, statistics
from app.api import shunting_data, shunting_questions
from app.api import lab_topics
from app.api import management
from app.api import simulation_console
from app.api import chapter_bank
from app.api import knowledge
from app.api import learning_records, operations, operation_learning, exams, theory_console
from app.services.account_upgrade import upgrade_accounts
from app.services.study_scope import retire_study_scope
from app.services import exams as exam_service
from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.services.interlocking.seed_service import seed_default_station
import app.models  # noqa: F401 - imported so metadata includes all ORM tables

# Multipart uploads spill to disk above Starlette's memory threshold. Keep those
# automatically removed spool files inside the project, alongside other runtime data.
UPLOAD_TEMP_DIR = Path(__file__).resolve().parents[2] / '.runtime/tmp/backend-uploads'
UPLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(UPLOAD_TEMP_DIR)

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

    retire_study_scope(engine)
    upgrade_accounts(engine)
    from app.services.operation_assessment.upgrade import upgrade as upgrade_assessment
    upgrade_assessment(engine)
    Base.metadata.create_all(bind=engine)
    from app.services.knowledge_library import adopt_builtin
    with SessionLocal() as db:
        adopt_builtin(db)
    _ensure_default_admin()
    with SessionLocal() as db:
        seed_default_station(db)
    # Insert missing collection records only; existing teaching content is preserved.
    from app.services.chapter_bank import import_bank, load_bank
    with SessionLocal() as db:
        import_bank(db, load_bank())
        db.commit()


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
app.include_router(knowledge.router, prefix='/api/admin/knowledge', tags=['knowledge-library'])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(shunting_data.router, prefix="/api/exam/shunting", tags=["shunting-data"])
app.include_router(shunting_questions.router, prefix="/api/exam/shunting", tags=["shunting-questions"])
app.include_router(lab_topics.router, prefix="/api/lab-topics", tags=["lab-topics"])
app.include_router(management.router, prefix="/api/management", tags=["management"])
app.include_router(simulation_console.router, prefix="/api/simulation-console", tags=["simulation-console"])
app.include_router(chapter_bank.router, prefix="/api/chapter-bank", tags=["chapter-bank"])
app.include_router(learning_records.router, prefix="/api/learning-records", tags=["learning-records"])


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    errors = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})

app.include_router(operations.router, prefix='/api/operations', tags=['operation-authoring'])
app.include_router(operation_learning.router, prefix='/api/operation-learning', tags=['operation-learning'])
app.include_router(exams.router, prefix='/api/exams', tags=['formal-exams'])

def _settle_exams():
    with SessionLocal() as db, exam_service.ops.LOCK:
        exam_service.settle_all(db)

async def _exam_clock():
    while True:
        await asyncio.sleep(1)
        try:
            await asyncio.to_thread(_settle_exams)
        except Exception:
            logging.getLogger(__name__).exception('考试到期结算失败，下次轮询重试')

@app.on_event('startup')
async def start_exam_clock():
    _settle_exams()
    app.state.exam_clock = asyncio.create_task(_exam_clock())

@app.on_event('shutdown')
async def stop_exam_clock():
    task = getattr(app.state, 'exam_clock', None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
app.include_router(theory_console.router, prefix='/api/lab-topics', tags=['topic-standard-station'])
