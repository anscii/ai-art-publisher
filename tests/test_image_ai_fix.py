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
    def test_returns_preview_url_and_temp_key(self, client, db):
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        storage = _mock_storage()
        storage.upload_bytes.return_value = "tmp/abc.png"

        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "make it darker"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["temp_key"].startswith(f"tmp/{_uid(db)}/")
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

    def test_404_for_missing_image(self, client, db):
        resp = client.post(
            "/api/images/nonexistent/ai-fix/keep",
            json={"temp_key": _my_temp_key(client, db)},
        )
        assert resp.status_code == 404


def _uid(db) -> str:
    from app.models import User

    return db.query(User).one().id


def _my_temp_key(client, db) -> str:
    from app.models import User

    client.get("/api/me")  # ensures the local user exists
    return f"tmp/{db.query(User).one().id}/12345678-1234-1234-1234-123456789abc.png"


class TestAiFixDiscard:
    def test_deletes_temp_key(self, client, db):
        key = _my_temp_key(client, db)
        storage = _mock_storage()
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            resp = client.delete(f"/api/images/ai-fix/tmp?temp_key={key}")
        assert resp.status_code == 204
        storage.delete.assert_called_once_with(key)

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


class TestAiFixNonAdmin:
    def _setup(self, client, db):
        from app.models import Image, Series
        from tests.conftest import login_as

        u = login_as(client, db)
        self._uid = u.id
        s = Series(name="mine", user_id=u.id)
        db.add(s)
        db.commit()
        img = Image(series_id=s.id, r2_key="images/a.jpg", original_filename="a.jpg")
        db.add(img)
        db.commit()
        return img.id

    def test_preview_with_fake_ai(self, client, db):
        img_id = self._setup(client, db)
        with patch(
            "app.routers.image_ai_fix.get_storage_from_settings", return_value=_mock_storage()
        ):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "fix"})
        assert resp.status_code == 200

    def test_no_key_gets_settings_hint(self, client, db, monkeypatch):
        monkeypatch.setattr(AppConfig, "fake_ai", False)
        img_id = self._setup(client, db)
        with patch(
            "app.routers.image_ai_fix.get_storage_from_settings", return_value=_mock_storage()
        ):
            resp = client.post(f"/api/images/{img_id}/ai-fix", json={"hint": "fix"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == (
            "Fix with AI needs your own OpenAI or Google key. Add one in Settings."
        )

    def test_own_key_is_used(self, client, db, monkeypatch):
        monkeypatch.setattr(AppConfig, "fake_ai", False)
        img_id = self._setup(client, db)
        client.put("/api/me/settings", json={"openai_api_key": "sk-mine"})
        with (
            patch(
                "app.routers.image_ai_fix.get_storage_from_settings",
                return_value=_mock_storage(),
            ),
            patch("app.services.ai.image_edit.edit_image", return_value=(b"x", 0.01)) as ed,
        ):
            resp = client.post(
                f"/api/images/{img_id}/ai-fix", json={"hint": "fix", "model": "gpt-image-2"}
            )
        assert resp.status_code == 200, resp.text
        assert ed.call_args.args[1] == "sk-mine"

    def test_keep_and_discard_not_forbidden(self, client, db):
        img_id = self._setup(client, db)
        key = f"tmp/{self._uid}/" + "0" * 36 + ".png"
        with patch(
            "app.routers.image_ai_fix.get_storage_from_settings", return_value=_mock_storage()
        ):
            keep = client.post(f"/api/images/{img_id}/ai-fix/keep", json={"temp_key": key})
            discard = client.delete(f"/api/images/ai-fix/tmp?temp_key={key}")
        assert keep.status_code == 200
        assert discard.status_code == 204


class TestAiFixTempKeyOwnership:
    def test_other_users_temp_key_rejected(self, client, db):
        from tests.conftest import login_as

        a = login_as(client, db, "a@example.com", "g-a")
        key = f"tmp/{a.id}/" + "1" * 36 + ".png"
        b = login_as(client, db, "b@example.com", "g-b")
        # B owns an image so only the key can be at fault
        from app.models import Image, Series

        ser = Series(name="b", user_id=b.id)
        db.add(ser)
        db.commit()
        img = Image(series_id=ser.id, r2_key="images/b.jpg", original_filename="b.jpg")
        db.add(img)
        db.commit()
        img_id = img.id
        storage = _mock_storage()
        with patch("app.routers.image_ai_fix.get_storage_from_settings", return_value=storage):
            keep = client.post(f"/api/images/{img_id}/ai-fix/keep", json={"temp_key": key})
            discard = client.delete(f"/api/images/ai-fix/tmp?temp_key={key}")
        assert keep.status_code == 400
        assert discard.status_code == 400
        storage.copy.assert_not_called()
        storage.delete.assert_not_called()

    def test_old_style_key_rejected(self, client, db):
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        key = "tmp/" + "0" * 36 + ".png"
        assert (
            client.post(f"/api/images/{img_id}/ai-fix/keep", json={"temp_key": key}).status_code
            == 400
        )
        assert client.delete(f"/api/images/ai-fix/tmp?temp_key={key}").status_code == 400


class TestAiFixLedger:
    def test_success_records_image_fix_row(self, client, db, monkeypatch):
        from app.models import AIRequest

        monkeypatch.setattr(AppConfig, "fake_ai", False)
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        client.put("/api/me/settings", json={"openai_api_key": "sk-mine"})
        with (
            patch(
                "app.routers.image_ai_fix.get_storage_from_settings",
                return_value=_mock_storage(),
            ),
            patch("app.services.ai.image_edit.edit_image", return_value=(b"x", 0.04)),
        ):
            resp = client.post(
                f"/api/images/{img_id}/ai-fix", json={"hint": "fix", "model": "gpt-image-2"}
            )
        assert resp.status_code == 200
        assert resp.json()["temp_key"].startswith(f"tmp/{_uid(db)}/")
        db.expire_all()
        (row,) = db.query(AIRequest).all()
        assert row.kind == "image_fix"
        assert row.via_default_access is False
        assert row.cost_usd == pytest.approx(0.04)
        assert row.model == "gpt-image-2"

    def test_failed_edit_records_nothing(self, client, db, monkeypatch):
        from app.models import AIRequest

        monkeypatch.setattr(AppConfig, "fake_ai", False)
        sid = _make_series(client)
        img_id = _register_image(client, sid)
        client.put("/api/me/settings", json={"openai_api_key": "sk-mine"})
        with (
            patch(
                "app.routers.image_ai_fix.get_storage_from_settings",
                return_value=_mock_storage(),
            ),
            patch("app.services.ai.image_edit.edit_image", side_effect=RuntimeError("boom")),
        ):
            resp = client.post(
                f"/api/images/{img_id}/ai-fix", json={"hint": "fix", "model": "gpt-image-2"}
            )
        assert resp.status_code == 502
        assert db.query(AIRequest).count() == 0
