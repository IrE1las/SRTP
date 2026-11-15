"""Pytest fixtures for interlocking tests."""

import sys
import os
import atexit
from uuid import uuid4
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Importing the application and running startup must never use the personal DB.
TEST_DIRECTORY = ROOT_DIR.parents[1] / '.runtime' / 'isolated-tests'
TEST_DIRECTORY.mkdir(parents=True, exist_ok=True)
IMPORT_DATABASE = TEST_DIRECTORY / f'import-{uuid4().hex}.db'
os.environ['DATABASE_URL'] = f'sqlite:///{IMPORT_DATABASE.as_posix()}'
os.environ['SECRET_KEY'] = 'isolated-workflow-tests-only'
os.environ['DEEPSEEK_API_KEY'] = ''

from app.core.database import Base, get_db
from app.models import *  # noqa: F403 - import all models for metadata
from app.services.interlocking.seed_service import reset_station_runtime_state, seed_default_station
from main import app


@atexit.register
def remove_import_database():
    from app.core.database import engine
    engine.dispose()
    IMPORT_DATABASE.unlink(missing_ok=True)


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Create an isolated SQLite database for each test."""

    db_path = tmp_path / "test_railway.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def seeded_station(db_session: Session) -> int:
    """Seed and reset the default station, returning its ID."""

    station = seed_default_station(db_session)
    reset_station_runtime_state(db_session, station.id)
    return station.id


@pytest.fixture()
def client(db_session: Session):
    """Create a FastAPI TestClient using the isolated database."""

    from fastapi.testclient import TestClient

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
