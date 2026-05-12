import shutil
from pathlib import Path

import boto3

from app.config import get_config

_LOCAL_URL_PREFIX = "/uploads"


class LocalStorageService:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir

    def public_url(self, key: str) -> str:
        return f"{_LOCAL_URL_PREFIX}/{key}"

    def upload_bytes(self, data: bytes, key: str, content_type: str = "image/jpeg") -> str:
        dest = self._dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return key

    def upload_file(self, filepath: str, key: str) -> str:
        dest = self._dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(filepath, dest)
        return key

    def download_bytes(self, key: str) -> bytes:
        return (self._dir / key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            (self._dir / key).unlink()
        except FileNotFoundError:
            pass


class R2StorageService:
    def __init__(
        self, endpoint: str, access_key: str, secret_key: str, bucket: str, public_base_url: str
    ):
        self._bucket = bucket
        self._base = public_base_url.rstrip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

    def public_url(self, key: str) -> str:
        return f"{self._base}/{key}"

    def upload_bytes(self, data: bytes, key: str, content_type: str = "image/jpeg") -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def upload_file(self, filepath: str, key: str) -> str:
        self._client.upload_file(filepath, self._bucket, key)
        return key

    def download_bytes(self, key: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


def get_public_base_url(settings) -> str:
    if get_config().local_storage:
        return _LOCAL_URL_PREFIX
    return settings.r2_public_base_url.rstrip("/")


def get_storage_from_settings(settings) -> R2StorageService | LocalStorageService:
    cfg = get_config()
    if cfg.local_storage:
        return LocalStorageService(Path(cfg.data_dir) / "uploads")
    return R2StorageService(
        endpoint=settings.r2_endpoint,
        access_key=settings.r2_access_key,
        secret_key=settings.r2_secret_key,
        bucket=settings.r2_bucket,
        public_base_url=settings.r2_public_base_url,
    )
