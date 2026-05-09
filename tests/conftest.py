from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as _db_module
from app.database import Base, get_db
from app.main import app

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    # Patch the module-level engine and session factory so that init_db() in the
    # FastAPI lifespan uses the test DB, not whatever DATABASE_URL points to locally.
    monkeypatch.setattr(_db_module, "engine", _engine)
    monkeypatch.setattr(_db_module, "SessionLocal", _TestingSessionLocal)
    monkeypatch.setattr(_db_module, "_bootstrap_settings", lambda db: None)
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db():
    session = _TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.public_url.side_effect = lambda key: f"https://pub.r2.dev/{key}"
    storage.upload_bytes.return_value = "images/test.jpg"
    storage.download_bytes.return_value = b"fake-image-data"
    return storage
