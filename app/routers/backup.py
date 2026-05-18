import gzip
import logging
import secrets
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from sqlalchemy.orm import Session

from app.config import get_config
from app.database import get_db
from app.routers.settings import get_or_create_settings

router = APIRouter(tags=["backup"])

_BACKUP_PREFIX = "backups/ai-art-publisher/db/"
_log = logging.getLogger("app.backup")


def _db_path() -> Path:
    url = get_config().database_url  # sqlite:///./data/db.sqlite
    return Path(url.split("///", 1)[-1]).resolve()


def _r2_client(settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key,
        aws_secret_access_key=settings.r2_secret_key,
        region_name="auto",
    )


@router.post("/internal/backup-db", include_in_schema=False)
def trigger_backup(request: Request, db: Session = Depends(get_db)):
    cfg = get_config()
    token = request.headers.get("X-Backup-Token", "")
    if not cfg.backup_token or not secrets.compare_digest(token, cfg.backup_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    settings = get_or_create_settings(db)
    if not settings.r2_endpoint or not settings.r2_access_key:
        raise HTTPException(status_code=500, detail="R2 not configured")

    _log.info("backup started")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}.sqlite.gz"
    key = f"{_BACKUP_PREFIX}{filename}"

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        tmp_path = Path(f.name)
    try:
        src = sqlite3.connect(str(_db_path()))
        dst = sqlite3.connect(str(tmp_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        raw = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    compressed = gzip.compress(raw)
    _log.info("backup compressed: %d bytes → %d bytes gzip", len(raw), len(compressed))

    s3 = _r2_client(settings)
    s3.put_object(
        Bucket=settings.r2_bucket,
        Key=key,
        Body=compressed,
        ContentType="application/gzip",
    )
    _log.info("backup uploaded: %s (%d bytes)", key, len(compressed))

    cutoff = datetime.now(timezone.utc) - timedelta(days=cfg.backup_retention_days)
    # list_objects_v2 returns up to 1000 objects; sufficient for ~2.7 years of daily backups
    resp = s3.list_objects_v2(Bucket=settings.r2_bucket, Prefix=_BACKUP_PREFIX)
    deleted = 0
    for obj in resp.get("Contents", []):
        if obj["LastModified"] < cutoff and obj["Key"] != key:
            s3.delete_object(Bucket=settings.r2_bucket, Key=obj["Key"])
            deleted += 1
    _log.info("backup cleanup: deleted %d old backup(s)", deleted)

    return {
        "status": "ok",
        "filename": filename,
        "size_bytes": len(compressed),
        "deleted_old": deleted,
    }
