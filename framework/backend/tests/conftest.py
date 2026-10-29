"""Project-local, isolated databases; application startup never touches a real database."""
import os
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT = ROOT_DIR.parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
(PROJECT / '.runtime/tests').mkdir(parents=True, exist_ok=True)
# Must happen before importing database, settings or main.
os.environ['DATABASE_URL'] = f"sqlite:///{(PROJECT / '.runtime/tests/import-only.db').as_posix()}"
os.environ['SECRET_KEY'] = 's1-test-key-not-for-production'
os.environ['DEEPSEEK_API_KEY'] = ''

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
import app.models
from main import app

@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'test_railway.db').as_posix()}", connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()

@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    startup = app.router.on_startup[:]
    app.router.on_startup.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup
