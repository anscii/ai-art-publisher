import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as _db_module
from app.config import AppConfig
from app.database import Base, get_db
from app.main import app

# ── E2E live server ────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
_E2E_PORT = 18765


def _wait_for_server(url: str, timeout: int = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=1)
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"Test server didn't start at {url}")


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("e2e") / "test.db"
    data_dir = tmp_path_factory.mktemp("e2e_data")
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "FAKE_POSTING": "true",
        "FAKE_AI": "true",
        "AUTH_USERNAME": "",
        "AUTH_PASSWORD": "",
        "DATA_DIR": str(data_dir),
        "LOCAL_STORAGE": "true",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(_E2E_PORT),
        ],
        env=env,
        cwd=str(_PROJECT_ROOT),
    )
    base = f"http://127.0.0.1:{_E2E_PORT}"
    try:
        _wait_for_server(f"{base}/health")
    except RuntimeError:
        proc.terminate()
        raise
    yield base
    proc.terminate()
    proc.wait()


_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def reset_fake_posting(monkeypatch):
    """Ensure FAKE_POSTING is always off in tests regardless of the local .env.
    AppConfig attributes are class-level (set at import time), so we patch the
    class attribute directly rather than relying on env var re-reads."""
    monkeypatch.setattr(AppConfig, "fake_posting", False)


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
