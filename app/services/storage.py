import boto3


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


def get_storage_from_settings(settings) -> R2StorageService:
    return R2StorageService(
        endpoint=settings.r2_endpoint,
        access_key=settings.r2_access_key,
        secret_key=settings.r2_secret_key,
        bucket=settings.r2_bucket,
        public_base_url=settings.r2_public_base_url,
    )
