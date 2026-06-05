from unittest.mock import MagicMock, patch

import pytest

from app.services.storage import LocalStorageService, R2StorageService


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


# --- LocalStorageService ---


@pytest.fixture
def local_svc(tmp_path):
    return LocalStorageService(tmp_path)


def test_local_public_url(local_svc):
    assert local_svc.public_url("images/abc.jpg") == "/uploads/images/abc.jpg"


def test_local_upload_and_download(local_svc, tmp_path):
    local_svc.upload_bytes(b"hello", "images/test.jpg", "image/jpeg")
    assert (tmp_path / "images" / "test.jpg").read_bytes() == b"hello"
    assert local_svc.download_bytes("images/test.jpg") == b"hello"


def test_local_upload_file(local_svc, tmp_path):
    src = tmp_path / "src.jpg"
    src.write_bytes(b"pixels")
    local_svc.upload_file(str(src), "images/copy.jpg")
    assert local_svc.download_bytes("images/copy.jpg") == b"pixels"


def test_local_delete(local_svc, tmp_path):
    local_svc.upload_bytes(b"data", "images/del.jpg", "image/jpeg")
    local_svc.delete("images/del.jpg")
    assert not (tmp_path / "images" / "del.jpg").exists()


def test_local_delete_nonexistent(local_svc):
    local_svc.delete("images/ghost.jpg")  # no error


def test_local_download_missing(local_svc):
    with pytest.raises(FileNotFoundError):
        local_svc.download_bytes("images/missing.jpg")


def test_local_copy(local_svc):
    local_svc.upload_bytes(b"original", "images/src.jpg", "image/jpeg")
    local_svc.copy("images/src.jpg", "images/dst.jpg")
    assert local_svc.download_bytes("images/dst.jpg") == b"original"


def test_local_traversal_blocked(local_svc):
    with pytest.raises(ValueError, match="escapes storage root"):
        local_svc._safe_path("../../etc/passwd")


def test_local_copy_traversal_blocked(local_svc):
    local_svc.upload_bytes(b"data", "images/real.jpg", "image/jpeg")
    with pytest.raises(ValueError, match="escapes storage root"):
        local_svc.copy("images/real.jpg", "../../evil.jpg")


def test_local_delete_traversal_blocked(local_svc):
    with pytest.raises(ValueError, match="escapes storage root"):
        local_svc.delete("../../etc/passwd")
