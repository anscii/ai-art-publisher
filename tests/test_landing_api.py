"""Tests for GET /api/landing/recent and landing page HTML."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.config import AppConfig
from app.models import Image, Post, PostImage, Series


def _series(db, title="Test Series") -> Series:
    s = Series(id=str(uuid.uuid4()), title=title)
    db.add(s)
    db.flush()
    return s


def _post(
    db,
    series,
    platform="instagram",
    title="Test Post",
    status="posted",
    posted_at=None,
    deleted_at=None,
    post_url=None,
    title_ru=None,
) -> Post:
    p = Post(
        id=str(uuid.uuid4()),
        series_id=series.id,
        platform=platform,
        title=title,
        title_ru=title_ru,
        description="",
        tags="[]",
        status=status,
        posted_at=posted_at or datetime.utcnow(),
        deleted_at=deleted_at,
        post_url=post_url,
    )
    db.add(p)
    db.flush()
    return p


def _image(db, series, r2_key="images/test.jpg") -> Image:
    img = Image(
        id=str(uuid.uuid4()),
        series_id=series.id,
        r2_key=r2_key,
        original_filename="test.jpg",
    )
    db.add(img)
    db.flush()
    return img


def _post_image(db, post, image, order_index=0) -> PostImage:
    pi = PostImage(post_id=post.id, image_id=image.id, order_index=order_index)
    db.add(pi)
    db.flush()
    return pi


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_landing_recent_empty_db(client):
    resp = client.get("/api/landing/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["posts"] == []
    assert data["total_posted"] == 0


def test_landing_recent_returns_4_most_recent(client, db):
    s = _series(db)
    now = datetime.utcnow()
    posts = []
    for i in range(6):
        p = _post(db, s, title=f"Post {i}", posted_at=now - timedelta(hours=i))
        posts.append(p)
    db.commit()

    resp = client.get("/api/landing/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["posts"]) == 4
    # Most recent first — Post 0 is newest
    titles = [card["title"] for card in data["posts"]]
    assert titles == ["Post 0", "Post 1", "Post 2", "Post 3"]


def test_landing_recent_excludes_non_posted(client, db):
    s = _series(db)
    _post(db, s, title="Published", status="posted")
    _post(db, s, title="Draft", status="draft")
    _post(db, s, title="Scheduled", status="scheduled")
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "Published"
    assert data["total_posted"] == 1


def test_landing_recent_excludes_deleted(client, db):
    s = _series(db)
    _post(db, s, title="Deleted", status="posted", deleted_at=datetime.utcnow())
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert data["posts"] == []
    assert data["total_posted"] == 0


def test_landing_recent_total_count_correct(client, db):
    s = _series(db)
    for _ in range(5):
        _post(db, s, status="posted")
    for _ in range(2):
        _post(db, s, status="draft")
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert data["total_posted"] == 5


def test_landing_recent_thumbnail_from_first_image(client, db):
    s = _series(db)
    p = _post(db, s, status="posted")
    img = _image(db, s, r2_key="images/photo.jpg")
    _post_image(db, p, img, order_index=0)
    db.commit()

    mock_settings = MagicMock()
    mock_settings.r2_public_base_url = "https://pub.r2.dev"
    mock_settings.local_storage = False

    with (
        patch("app.routers.landing.get_or_create_settings", return_value=mock_settings),
        patch("app.routers.landing.get_public_base_url", return_value="https://pub.r2.dev"),
    ):
        resp = client.get("/api/landing/recent")

    data = resp.json()
    assert len(data["posts"]) == 1
    thumb = data["posts"][0]["thumbnail_url"]
    assert thumb is not None
    assert thumb.startswith("https://pub.r2.dev/")
    assert "photo.jpg" in thumb


def test_landing_recent_no_images_thumb_null(client, db):
    s = _series(db)
    _post(db, s, status="posted")
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["thumbnail_url"] is None


def test_landing_recent_post_url_passed_through(client, db):
    s = _series(db)
    _post(db, s, status="posted", post_url="https://instagram.com/p/ABC/")
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["post_url"] == "https://instagram.com/p/ABC/"


def test_landing_recent_is_public(client, monkeypatch):
    monkeypatch.setattr(AppConfig, "auth_username", "user")
    monkeypatch.setattr(AppConfig, "auth_password", "pass")

    # No auth cookie — endpoint must still return 200
    resp = client.get("/api/landing/recent")
    assert resp.status_code == 200


def test_landing_recent_title_ru_fallback(client, db):
    s = _series(db)
    _post(db, s, title="", title_ru="Лес", status="posted")
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "Лес"


def test_landing_recent_description_included(client, db):
    s = _series(db)
    p = _post(db, s, status="posted")
    p.description = "A hauntingly beautiful series of midnight forests."
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["description"] == "A hauntingly beautiful series of midnight forests."


def test_landing_recent_empty_description_is_null(client, db):
    s = _series(db)
    _post(db, s, status="posted")  # description="" by default
    db.commit()

    resp = client.get("/api/landing/recent")
    data = resp.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["description"] is None


def test_landing_html_has_dispatches_ids(client):
    resp = client.get("/landing")
    assert resp.status_code == 200
    assert 'id="aap-dispatches-grid"' in resp.text
    assert 'id="aap-dispatches-meta"' in resp.text


def test_landing_recent_skips_post_with_null_posted_at(client, db):
    """Posts with status='posted' but posted_at=NULL must not appear (would crash Pydantic)."""
    s = _series(db)
    # null posted_at — simulates incomplete/corrupt post record
    p = Post(
        id=str(__import__("uuid").uuid4()),
        series_id=s.id,
        platform="instagram",
        title="Null date",
        description="",
        tags="[]",
        status="posted",
        posted_at=None,
    )
    db.add(p)
    db.commit()

    resp = client.get("/api/landing/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["posts"] == []
    assert data["total_posted"] == 0
