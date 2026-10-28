"""Application entry point for the staged learning and examination refactor."""
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api import admin, auth, settings, lab_topics, theory_console, operations
from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.services.s1_migration import require_current_schema
from app.services.s2_migration import require_account_schema
from app.services.s3_migration import require_operation_schema
from app.services.bootstrap import seed_theory
import app.models  # register only the retained tables

app = FastAPI(title='铁路计算机联锁仿真实训系统 API', version='0.2.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
DEFAULT_ADMIN_PASSWORD = '00000000'

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    # Pydantic's default error response can echo password/key values from request inputs.
    errors = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
              for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})

def _ensure_default_admin():
    with SessionLocal() as db:
        if db.query(User).filter(User.role == 'admin').first() is None:
            db.add(User(username='admin', password_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
                        real_name='管理员', role='admin', student_id=None, class_name=None))
            db.commit()

@app.on_event('startup')
def on_startup():
    # Existing databases require explicit, backed-up migration before any writes.
    require_current_schema(engine)
    require_account_schema(engine)
    require_operation_schema(engine)
    Base.metadata.create_all(bind=engine)
    _ensure_default_admin()
    with SessionLocal() as db:
        seed_theory(db)

@app.get('/api/health', tags=['health'])
def health_check():
    return {'status':'ok', 'service':'railway-interlocking-api', 'stage':'S3'}

app.include_router(operations.router, prefix='/api/operations', tags=['operations'])

app.include_router(auth.router, prefix='/api/auth', tags=['auth'])
app.include_router(admin.router, prefix='/api/admin', tags=['admin'])
app.include_router(settings.router, prefix='/api/settings', tags=['settings'])
app.include_router(lab_topics.router, prefix='/api/lab-topics', tags=['theory'])

app.include_router(theory_console.router, prefix='/api/lab-topics', tags=['theory-console'])
