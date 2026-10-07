import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.models import Image, Post, PostImage, Series, Story, StoryFrame
from app.routers.auth import require_admin
from tests.conftest import login_as
from tests.test_ownership import _fill

_POST_BODY = {
    "platforms": ["instagram"],
    "title": "t",
    "description_telegram": "d",
    "description_other": "d",
    "image_ids": ["{image_id}"],
}

GATED = [
    ("POST", "/api/series/{series_id}/images/register", {"r2_key": "k", "original_filename": "f"}),
    ("POST", "/api/posts/{post_id}/post", None),
    ("POST", "/api/posts/{post_id}/schedule", {"datetime_utc": "2030-01-01T00:00:00Z"}),
    ("DELETE", "/api/posts/{post_id}/schedule", None),
    ("POST", "/api/stories/{story_id}/publish", None),
]

# Lifting a stopgap in #2 / #5 must edit this set on purpose.
GATE_INVENTORY = frozenset(
    {
        ("DELETE", "/api/posts/{post_id}/schedule"),
        ("GET", "/api/settings"),
        ("GET", "/api/settings/pinterest/boards"),
        ("POST", "/api/posts/{post_id}/post"),
        ("POST", "/api/posts/{post_id}/schedule"),
        ("POST", "/api/series/{series_id}/images/register"),
        ("POST", "/api/settings/test/{service}"),
        ("POST", "/api/stories/{story_id}/publish"),
        ("PUT", "/api/settings"),
    }
)


@pytest.fixture
def mine(client, db):
    """Objects owned by a logged-in NON-admin user."""
    u = login_as(client, db, "u@example.com", "g-u")
    s = Series(user_id=u.id, title="s")
    db.add(s)
    db.flush()
    img = Image(series_id=s.id, r2_key="k", original_filename="f", order_index=0)
    post = Post(series_id=s.id, platform="instagram", status="scheduled")
    db.add_all([img, post])
    db.flush()
    db.add(PostImage(post_id=post.id, image_id=img.id, order_index=0))
    story = Story(post_id=post.id)
    db.add(story)
    db.flush()
    db.add(StoryFrame(story_id=story.id, position=0, frame_type="text"))
    db.commit()
    return {"series_id": s.id, "image_id": img.id, "post_id": post.id, "story_id": story.id}


@pytest.mark.parametrize("method,path,body", GATED, ids=[f"{m} {p}" for m, p, _ in GATED])
def test_non_admin_owner_gets_403(client, mine, method, path, body):
    kwargs = {} if body is None else {"json": _fill(body, mine)}
    resp = client.request(method, path.format(**mine), **kwargs)
    assert resp.status_code == 403, resp.text


def test_create_posts_scheduled_requires_admin(client, db, mine):
    url = f"/api/series/{mine['series_id']}/posts"
    body = _fill(_POST_BODY, mine)
    resp = client.post(url, json={**body, "scheduled_at": "2030-01-01T00:00:00Z"})
    assert resp.status_code == 403
    assert db.query(Post).filter(Post.platform == "instagram").count() == 1  # only the fixture's

    assert client.post(url, json=body).status_code == 201


def test_create_posts_scheduled_as_admin(client, db):
    u = login_as(client, db, "adm@example.com", "g-adm", is_admin=True)
    s = Series(user_id=u.id, title="s")
    db.add(s)
    db.flush()
    img = Image(series_id=s.id, r2_key="k", original_filename="f", order_index=0)
    db.add(img)
    db.commit()
    body = _fill(_POST_BODY, {"image_id": img.id})
    resp = client.post(
        f"/api/series/{s.id}/posts", json={**body, "scheduled_at": "2030-01-01T00:00:00Z"}
    )
    assert resp.status_code == 201
    assert resp.json()[0]["status"] == "scheduled"


def test_gate_inventory():
    def _deps(d):
        return {d.call} | {c for sub in d.dependencies for c in _deps(sub)}

    actual = {
        (m, r.path)
        for r in app.routes
        if isinstance(r, APIRoute)
        and r.path.startswith("/api/")
        and require_admin in _deps(r.dependant)
        for m in r.methods - {"HEAD", "OPTIONS"}
    }
    assert actual == GATE_INVENTORY


@pytest.mark.parametrize("is_admin", [True, False])
def test_me(client, db, is_admin):
    login_as(client, db, "m@example.com", "g-m", is_admin=is_admin)
    assert client.get("/api/me").json() == {"email": "m@example.com", "is_admin": is_admin}


def test_me_unauthenticated_401(client, auth_config):
    assert client.get("/api/me").status_code == 401
