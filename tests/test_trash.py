from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.models import AIVariant, Image, Series


def _now():
    return datetime.now(timezone.utc)


def _series(db, title="S", deleted=False):
    s = Series(title=title, original_folder_name=title, deleted_at=_now() if deleted else None)
    db.add(s)
    db.flush()
    return s


def _image(db, series_id, key="images/x.jpg", deleted=False):
    img = Image(
        series_id=series_id,
        r2_key=key,
        original_filename=key.split("/")[-1],
        deleted_at=_now() if deleted else None,
    )
    db.add(img)
    db.flush()
    return img


def _variant(db, series_id, provider="anthropic", model="claude", deleted=False):
    v = AIVariant(
        series_id=series_id,
        provider=provider,
        model=model,
        title="Test variant",
        deleted_at=_now() if deleted else None,
    )
    db.add(v)
    db.flush()
    return v


def _storage_ok():
    m = MagicMock()
    m.delete.return_value = None
    return m


def _storage_fail(exc=None):
    m = MagicMock()
    m.delete.side_effect = exc or RuntimeError("S3 error")
    return m


# ── permanently_delete_image ──────────────────────────────────────────────────


def test_permanently_delete_image_success(client, db):
    s = _series(db)
    img = _image(db, s.id, deleted=True)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_ok()):
        resp = client.delete(f"/api/trash/images/{img.id}")

    assert resp.status_code == 200
    assert db.get(Image, img.id) is None


def test_permanently_delete_image_storage_fail_returns_500(client, db):
    s = _series(db)
    img = _image(db, s.id, deleted=True)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_fail()):
        resp = client.delete(f"/api/trash/images/{img.id}")

    assert resp.status_code == 500
    assert db.get(Image, img.id) is not None


def test_permanently_delete_image_not_found(client, db):
    resp = client.delete("/api/trash/images/nonexistent")
    assert resp.status_code == 404


# ── permanently_delete_series ─────────────────────────────────────────────────


def test_permanently_delete_series_success(client, db):
    s = _series(db, deleted=True)
    _image(db, s.id)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_ok()):
        resp = client.delete(f"/api/trash/series/{s.id}")

    assert resp.status_code == 200
    assert db.get(Series, s.id) is None


def test_permanently_delete_series_image_storage_fail_returns_500(client, db):
    s = _series(db, deleted=True)
    _image(db, s.id)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_fail()):
        resp = client.delete(f"/api/trash/series/{s.id}")

    assert resp.status_code == 500
    assert db.get(Series, s.id) is not None


def test_permanently_delete_series_not_found(client, db):
    resp = client.delete("/api/trash/series/nonexistent")
    assert resp.status_code == 404


# ── empty_trash ───────────────────────────────────────────────────────────────


def test_empty_trash_success(client, db):
    s = _series(db, deleted=True)
    _image(db, s.id)
    live_series = _series(db, title="Live")
    img_standalone = _image(db, live_series.id, key="images/b.jpg", deleted=True)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_ok()):
        resp = client.delete("/api/trash")

    assert resp.status_code == 200
    assert db.get(Series, s.id) is None
    assert db.get(Image, img_standalone.id) is None


def test_empty_trash_series_with_storage_fail_skipped(client, db):
    good_series = _series(db, title="Good", deleted=True)
    _image(db, good_series.id, key="images/good.jpg")
    bad_series = _series(db, title="Bad", deleted=True)
    bad_img = _image(db, bad_series.id, key="images/bad.jpg")
    db.commit()

    storage = MagicMock()
    storage.delete.side_effect = (
        lambda key: (_ for _ in ()).throw(RuntimeError("fail")) if "bad" in key else None
    )

    with patch("app.routers.trash.get_storage_from_settings", return_value=storage):
        resp = client.delete("/api/trash")

    assert resp.status_code == 200
    assert db.get(Series, good_series.id) is None
    assert db.get(Series, bad_series.id) is not None
    assert db.get(Image, bad_img.id) is not None


def test_empty_trash_standalone_image_storage_fail_skipped(client, db):
    live = _series(db, title="Live")
    ok_img = _image(db, live.id, key="images/ok.jpg", deleted=True)
    fail_img = _image(db, live.id, key="images/fail.jpg", deleted=True)
    db.commit()

    storage = MagicMock()
    storage.delete.side_effect = (
        lambda key: (_ for _ in ()).throw(RuntimeError("fail")) if "fail" in key else None
    )

    with patch("app.routers.trash.get_storage_from_settings", return_value=storage):
        resp = client.delete("/api/trash")

    assert resp.status_code == 200
    assert db.get(Image, ok_img.id) is None
    assert db.get(Image, fail_img.id) is not None


# ── variant trash ─────────────────────────────────────────────────────────────


def test_trash_lists_deleted_variant(client, db):
    s = _series(db)
    v = _variant(db, s.id, deleted=True)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_ok()):
        data = client.get("/api/trash").json()

    assert any(item["id"] == v.id for item in data["variants"])


def test_trash_does_not_list_variant_of_deleted_series(client, db):
    s = _series(db, deleted=True)
    _variant(db, s.id, deleted=True)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_ok()):
        data = client.get("/api/trash").json()

    assert data["variants"] == []


def test_restore_variant(client, db):
    s = _series(db)
    v = _variant(db, s.id, deleted=True)
    db.commit()

    resp = client.post(f"/api/trash/variants/{v.id}/restore")
    assert resp.status_code == 200

    db.refresh(v)
    assert v.deleted_at is None


def test_restore_variant_not_found(client):
    resp = client.post("/api/trash/variants/nonexistent/restore")
    assert resp.status_code == 404


def test_permanently_delete_variant(client, db):
    s = _series(db)
    v = _variant(db, s.id, deleted=True)
    db.commit()

    resp = client.delete(f"/api/trash/variants/{v.id}")
    assert resp.status_code == 200
    assert db.get(AIVariant, v.id) is None


def test_permanently_delete_variant_not_found(client):
    resp = client.delete("/api/trash/variants/nonexistent")
    assert resp.status_code == 404


def test_empty_trash_deletes_variants(client, db):
    live = _series(db, title="Live")
    v = _variant(db, live.id, deleted=True)
    db.commit()

    with patch("app.routers.trash.get_storage_from_settings", return_value=_storage_ok()):
        resp = client.delete("/api/trash")

    assert resp.status_code == 200
    assert db.get(AIVariant, v.id) is None
