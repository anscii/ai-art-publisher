from unittest.mock import MagicMock, patch

import pytest

from app.config import AppConfig


def _make_series(client, title="S"):
    return client.post("/api/series", json={"title": title}).json()["id"]


def _register_image(client, series_id, key="images/test.jpg"):
    return client.post(
        f"/api/series/{series_id}/images/register",
        json={"r2_key": key, "original_filename": "test.jpg"},
    ).json()["id"]


def _mock_storage(download_data=b"fake-image-bytes"):
    storage = MagicMock()
    storage.download_bytes.return_value = download_data
    storage.upload_bytes.return_value = "tmp/fake-uuid.png"
    storage.public_url.side_effect = lambda key: f"https://pub.r2.dev/{key}"
    storage.copy.return_value = "images/new-uuid.png"
    return storage


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    monkeypatch.setattr(AppConfig, "fake_ai", True)
    monkeypatch.setattr(AppConfig, "local_storage", False)


class TestAiFixPreview:
    def test_returns_preview_url_and_temp_key(self, client):
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        storage = _mock_storage()
        storage.upload_bytes.return_value = "tmp/abc.png"

        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "make it darker"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["temp_key"].startswith("tmp/")
        assert "preview_url" in data
        storage.download_bytes.assert_called_once()
        storage.upload_bytes.assert_called_once()

    def test_404_for_missing_image(self, client):
        resp = client.post("/api/images/nonexistent/ai-fix", json={"hint": "fix"})
        assert resp.status_code == 404

    def test_404_for_deleted_image(self, client, db):
        from datetime import datetime

        from app.models import Image

        sid = _make_series(client)
        img_id = _register_image(client, sid)
        img = db.get(Image, img_id)
        img.deleted_at = datetime.utcnow()
        db.commit()

        storage = _mock_storage()
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "fix"})
        assert resp.status_code == 404

    def test_requires_openai_key_when_not_fake(self, client, monkeypatch):
        monkeypatch.setattr(AppConfig, "fake_ai", False)
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        storage = _mock_storage()
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "fix"})
        assert resp.status_code == 400
        assert "OpenAI" in resp.json()["detail"]


class TestAiFixKeep:
    def test_creates_new_image_after_source(self, client):
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        storage = _mock_storage()

        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            preview = client.post(
                f"/api/images/{img_id}/ai-fix", json={"hint": "make it brighter"}
            ).json()
            temp_key = preview["temp_key"]

            resp = client.post(f"/api/images/{img_id}/ai-fix/keep", json={"temp_key": temp_key})

        assert resp.status_code == 200
        series = resp.json()
        images = series["images"]
        assert len(images) == 2
        storage.copy.assert_called_once()
        storage.delete.assert_called()

    def test_kept_image_filename_prefixed(self, client, db):
        from app.models import Image

        sid = _make_series(client)
        img_id = _register_image(client, sid, key="images/original.jpg")

        storage = _mock_storage()
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            preview = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "fix"}).json()
            client.post(f"/api/images/{img_id}/ai-fix/keep", json={"temp_key": preview["temp_key"]})

        db.expire_all()
        new_img = (
            db.query(Image).filter_by(series_id=sid).order_by(Image.order_index.desc()).first()
        )
        assert new_img.original_filename.startswith("ai-fix-")

    def test_storage_error_on_keep_returns_502(self, client):
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        storage = _mock_storage()
        storage.copy.side_effect = Exception("R2 network error")

        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            preview = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "fix"}).json()
            resp = client.post(
                f"/api/images/{img_id}/ai-fix/keep", json={"temp_key": preview["temp_key"]}
            )
        assert resp.status_code == 502
        assert "Try again" in resp.json()["detail"]

    def test_new_image_inserted_after_source(self, client, db):
        from app.models import Image

        sid = _make_series(client)
        img1_id = _register_image(client, sid, key="images/one.jpg")
        img2_id = _register_image(client, sid, key="images/two.jpg")

        # Set explicit order indices
        img1 = db.get(Image, img1_id)
        img2 = db.get(Image, img2_id)
        img1.order_index = 0
        img2.order_index = 1
        db.commit()

        storage = _mock_storage()
        storage.upload_bytes.return_value = "tmp/preview.png"

        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            preview = client.post(f"/api/images/{img1_id}/ai-fix", json={"hint": "fix"}).json()
            client.post(
                f"/api/images/{img1_id}/ai-fix/keep", json={"temp_key": preview["temp_key"]}
            )

        db.expire_all()
        img2_refreshed = db.get(Image, img2_id)
        # img2 should have been shifted from order_index=1 to order_index=2
        assert img2_refreshed.order_index == 2

    def test_rejects_invalid_temp_key(self, client):
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        resp = client.post(
            f"/api/images/{img_id}/ai-fix/keep", json={"temp_key": "images/evil.jpg"}
        )
        assert resp.status_code == 400

    def test_404_for_missing_image(self, client):
        resp = client.post(
            "/api/images/nonexistent/ai-fix/keep",
            json={"temp_key": _VALID_TEMP_KEY},
        )
        assert resp.status_code == 404


_VALID_TEMP_KEY = "tmp/12345678-1234-1234-1234-123456789abc.png"


class TestAiFixDiscard:
    def test_deletes_temp_key(self, client):
        storage = _mock_storage()
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.delete(f"/api/images/ai-fix/tmp?temp_key={_VALID_TEMP_KEY}")
        assert resp.status_code == 204
        storage.delete.assert_called_once_with(_VALID_TEMP_KEY)

    def test_rejects_non_tmp_key(self, client):
        storage = _mock_storage()
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.delete("/api/images/ai-fix/tmp?temp_key=images/real.jpg")
        assert resp.status_code == 400
        storage.delete.assert_not_called()

    def test_rejects_traversal_key(self, client):
        storage = _mock_storage()
        traversal = "tmp/../../etc/passwd"
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.delete(f"/api/images/ai-fix/tmp?temp_key={traversal}")
        assert resp.status_code == 400
        storage.delete.assert_not_called()

    def test_rejects_keep_traversal(self, client):
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        resp = client.post(
            f"/api/images/{img_id}/ai-fix/keep",
            json={"temp_key": "tmp/../../images/real.jpg"},
        )
        assert resp.status_code == 400
