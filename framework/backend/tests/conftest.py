"""Pytest fixtures for interlocking tests."""

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import Base, get_db
from app.models import *  # noqa: F403 - import all models for metadata
from app.services.interlocking.seed_service import reset_station_runtime_state, seed_default_station
from main import app


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
