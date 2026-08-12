import os
import tempfile
import atexit

import pytest
from fastapi.testclient import TestClient

# ── Set test DB BEFORE importing app ──────────────────────────────
_db_fd, _db_path = tempfile.mkstemp(suffix=".db", prefix="sd_test_")
os.environ["SD_DATABASE_URL"] = f"sqlite:///{_db_path}"

from app.main import app
from app.core.database import SessionLocal, Base, engine
from app.core.ratelimit import reset_rate_limits


def _cleanup():
    os.close(_db_fd)
    try:
        os.unlink(_db_path)
    except OSError:
        pass


atexit.register(_cleanup)


@pytest.fixture(autouse=True)
def setup_db():
    """Recreate tables before each test for isolation."""
    Base.metadata.create_all(bind=engine)
    reset_rate_limits()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
