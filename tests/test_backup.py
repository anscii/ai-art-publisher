import gzip
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models import AppSettings


@pytest.fixture
def backup_token():
    from app.config import get_config

    real = get_config()
    mock_cfg = MagicMock(wraps=real)
    mock_cfg.backup_token = "test-token"
    mock_cfg.backup_retention_days = 30
    with patch("app.routers.backup.get_config", return_value=mock_cfg):
        yield "test-token"


@pytest.fixture
def r2_settings(db):
    s = db.get(AppSettings, 1)
    if not s:
        s = AppSettings(id=1)
        db.add(s)
    s.r2_endpoint = "https://fake.r2.dev"
    s.r2_access_key = "key"
    s.r2_secret_key = "secret"
    s.r2_bucket = "test-bucket"
    db.commit()
    return s


@pytest.fixture
def real_db_file():
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = Path(f.name)
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE x (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    yield path
    path.unlink(missing_ok=True)


def test_backup_no_token(client):
    resp = client.post("/internal/backup-db")
    assert resp.status_code == 401


def test_backup_wrong_token(client, backup_token):
    resp = client.post("/internal/backup-db", headers={"X-Backup-Token": "wrong"})
    assert resp.status_code == 401


def test_backup_no_r2_config(client, backup_token, db):
    s = db.get(AppSettings, 1)
    if not s:
        s = AppSettings(id=1)
        db.add(s)
    s.r2_endpoint = ""
    s.r2_access_key = ""
    db.commit()
    resp = client.post("/internal/backup-db", headers={"X-Backup-Token": backup_token})
    assert resp.status_code == 500


def test_backup_success(client, backup_token, r2_settings, real_db_file):
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {"Contents": []}

    with (
        patch("app.routers.backup._db_path", return_value=real_db_file),
        patch("app.routers.backup._r2_client", return_value=mock_s3),
    ):
        resp = client.post("/internal/backup-db", headers={"X-Backup-Token": backup_token})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["filename"].endswith(".sqlite.gz")
    assert data["size_bytes"] > 0
    assert data["deleted_old"] == 0
    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Key"].startswith("backups/ai-art-publisher/db/")
    assert gzip.decompress(call_kwargs["Body"])  # valid gzip


def test_backup_retention_cleanup(client, backup_token, r2_settings, real_db_file):
    old_key = "backups/ai-art-publisher/db/2020-01-01_03-00-00.sqlite.gz"
    old_ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": old_key, "LastModified": old_ts}]}

    with (
        patch("app.routers.backup._db_path", return_value=real_db_file),
        patch("app.routers.backup._r2_client", return_value=mock_s3),
    ):
        resp = client.post("/internal/backup-db", headers={"X-Backup-Token": backup_token})

    assert resp.status_code == 200
    assert resp.json()["deleted_old"] == 1
    mock_s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key=old_key)
