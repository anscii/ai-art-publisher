from unittest.mock import MagicMock, patch

from app.services.storage import R2StorageService


def _svc():
    return R2StorageService(
        endpoint="https://fake.r2.dev",
        access_key="key",
        secret_key="secret",
        bucket="test-bucket",
        public_base_url="https://pub.r2.dev",
    )


def test_public_url():
    assert _svc().public_url("images/abc.jpg") == "https://pub.r2.dev/images/abc.jpg"


@patch("app.services.storage.boto3.client")
def test_upload_bytes(mock_boto):
    mock_client = MagicMock()
    mock_boto.return_value = mock_client
    _svc().upload_bytes(b"data", "images/test.jpg", "image/jpeg")
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="images/test.jpg",
        Body=b"data",
        ContentType="image/jpeg",
    )


@patch("app.services.storage.boto3.client")
def test_delete(mock_boto):
    mock_client = MagicMock()
    mock_boto.return_value = mock_client
    _svc().delete("images/test.jpg")
    mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="images/test.jpg")


@patch("app.services.storage.boto3.client")
def test_download_bytes(mock_boto):
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"img")}
    mock_boto.return_value = mock_client
    assert _svc().download_bytes("images/test.jpg") == b"img"
