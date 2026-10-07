from datetime import datetime, timezone

import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.models import (
    AIVariant,
    Collection,
    Image,
    Post,
    PostImage,
    Series,
    Story,
    StoryFrame,
)
from tests.conftest import login_as

_ROUTER_MODULES_WITH_STORAGE = ("images", "image_ai_fix", "stories", "generate", "trash")
_NOW = datetime.now(timezone.utc)


@pytest.fixture
def storage(mock_storage, monkeypatch):
    for m in _ROUTER_MODULES_WITH_STORAGE:
        monkeypatch.setattr(f"app.routers.{m}.get_storage_from_settings", lambda *_a: mock_storage)
    return mock_storage


@pytest.fixture
def graph(client, db):
    """User A's object graph (+ trashed rows); leaves the client logged in as user B."""
    a = login_as(client, db, "a@example.com", "g-a")
    col = Collection(name="c", user_id=a.id)
    db.add(col)
    db.flush()
    s = Series(user_id=a.id, collection_id=col.id, title="A series")
    ts = Series(user_id=a.id, title="trashed series", deleted_at=_NOW)
    db.add_all([s, ts])
    db.flush()
    img = Image(series_id=s.id, r2_key="a/img", original_filename="f", order_index=0)
    timg = Image(
        series_id=s.id, r2_key="a/timg", original_filename="f", order_index=1, deleted_at=_NOW
    )
    var = AIVariant(series_id=s.id, provider="p", model="m")
    tvar = AIVariant(series_id=s.id, provider="p", model="m", deleted_at=_NOW)
    post = Post(series_id=s.id, platform="instagram", status="scheduled", scheduled_at=_NOW)
    db.add_all([img, timg, var, tvar, post])
    db.flush()
    db.add(PostImage(post_id=post.id, image_id=img.id, order_index=0))
    story = Story(post_id=post.id)
    db.add(story)
    db.flush()
    frame = StoryFrame(story_id=story.id, position=0, frame_type="text")
    db.add(frame)
    db.commit()
    ids = {
        "collection_id": col.id,
        "series_id": s.id,
        "image_id": img.id,
        "variant_id": var.id,
        "post_id": post.id,
        "story_id": story.id,
        "frame_id": frame.id,
        "trashed_series_id": ts.id,
        "trashed_image_id": timg.id,
        "trashed_variant_id": tvar.id,
    }
    client.cookies.clear()
    login_as(client, db, "b@example.com", "g-b", is_admin=True)  # gates answer 403 to non-admins
    return ids


# (method, path_template, json_body) -- single source for the parametrization and the guard.
# Trash templates use the trashed_* ids via the aliases below.
_T = {
    "series_id": "trashed_series_id",
    "image_id": "trashed_image_id",
    "variant_id": "trashed_variant_id",
}
FOREIGN = [
    ("PATCH", "/api/collections/{collection_id}", {"name": "x"}),
    ("DELETE", "/api/collections/{collection_id}", None),
    ("GET", "/api/series/{series_id}", None),
    ("PUT", "/api/series/{series_id}", {"title": "x"}),
    ("DELETE", "/api/series/{series_id}", None),
    ("POST", "/api/series/{series_id}/generate", {}),
    ("POST", "/api/series/{series_id}/generate-full", {"description": "d"}),
    ("GET", "/api/series/{series_id}/generation-status", None),
    ("POST", "/api/series/{series_id}/images", "upload"),
    ("POST", "/api/series/{series_id}/images/register", {"r2_key": "k", "original_filename": "f"}),
    ("PUT", "/api/series/{series_id}/images/reorder", {"image_ids": ["{image_id}"]}),
    ("GET", "/api/series/{series_id}/posts", None),
    (
        "POST",
        "/api/series/{series_id}/posts",
        {
            "platforms": ["instagram"],
            "title": "t",
            "description_telegram": "d",
            "description_other": "d",
            "image_ids": ["{image_id}"],
        },
    ),
    ("PUT", "/api/series/{series_id}/queue", {"image_ids": ["{image_id}"]}),
    ("DELETE", "/api/images/{image_id}", None),
    ("PUT", "/api/images/{image_id}/move", {"target_series_id": "{series_id}"}),
    ("PATCH", "/api/images/{image_id}/status", {"status": "skip"}),
    ("POST", "/api/images/{image_id}/ai-fix", {"hint": "h"}),
    ("POST", "/api/images/{image_id}/ai-fix/keep", {"temp_key": "tmp/" + "0" * 36 + ".png"}),
    ("DELETE", "/api/ai_variants/{variant_id}", None),
    ("PATCH", "/api/ai_variants/{variant_id}", {"instagram_seo": "x"}),
    ("GET", "/api/posts/{post_id}", None),
    ("PATCH", "/api/posts/{post_id}", {"title": "x"}),
    ("DELETE", "/api/posts/{post_id}", None),
    ("POST", "/api/posts/{post_id}/post", None),
    ("POST", "/api/posts/{post_id}/schedule", {"datetime_utc": "2030-01-01T00:00:00Z"}),
    ("DELETE", "/api/posts/{post_id}/schedule", None),
    ("POST", "/api/posts/{post_id}/stories", {"image_ids": ["{image_id}"]}),
    ("GET", "/api/stories/{story_id}", None),
    ("PATCH", "/api/stories/{story_id}", {"link_area": None}),
    ("POST", "/api/stories/{story_id}/frames", None),
    ("POST", "/api/stories/{story_id}/publish", None),
    ("POST", "/api/stories/{story_id}/render", None),
    ("POST", "/api/stories/{story_id}/reorder", {"frame_ids": ["{frame_id}"]}),
    ("PATCH", "/api/story-frames/{frame_id}", {"text": "x"}),
    ("DELETE", "/api/trash/images/{image_id}", None),
    ("POST", "/api/trash/images/{image_id}/restore", None),
    ("DELETE", "/api/trash/series/{series_id}", None),
    ("POST", "/api/trash/series/{series_id}/restore", None),
    ("DELETE", "/api/trash/variants/{variant_id}", None),
    ("POST", "/api/trash/variants/{variant_id}/restore", None),
]


def _fill(obj, ids):
    if isinstance(obj, str):
        return obj.format(**ids)
    if isinstance(obj, list):
        return [_fill(o, ids) for o in obj]
    if isinstance(obj, dict):
        return {k: _fill(v, ids) for k, v in obj.items()}
    return obj


@pytest.mark.parametrize("method,path,body", FOREIGN, ids=[f"{m} {p}" for m, p, _ in FOREIGN])
def test_foreign_object_404s(client, graph, storage, method, path, body):
    ids = dict(graph)
    if path.startswith("/api/trash/"):  # trash routes act on trashed rows
        ids.update({k: graph[v] for k, v in _T.items()})
    kwargs = {}
    if body == "upload":
        kwargs["files"] = [("files", ("a.jpg", b"x", "image/jpeg"))]
    elif body is not None:
        kwargs["json"] = _fill(body, ids)
    resp = client.request(method, path.format(**ids), **kwargs)
    assert resp.status_code == 404, resp.text
    storage.upload_bytes.assert_not_called()
    storage.delete.assert_not_called()


def _api_routes():
    return [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/")]


def test_foreign_table_covers_every_id_route():
    actual = {
        (m, r.path) for r in _api_routes() if "{" in r.path for m in r.methods - {"HEAD", "OPTIONS"}
    } - {
        ("POST", "/api/settings/test/{service}"),
        ("POST", "/api/me/settings/test/{provider}"),
    }
    assert {(m, p) for m, p, _ in FOREIGN} == actual


def test_every_api_route_requires_current_user():
    from app.routers.auth import get_current_user

    def _deps(d):
        return {d.call} | {c for sub in d.dependencies for c in _deps(sub)}

    missing = [
        r.path
        for r in _api_routes()
        if r.path != "/api/landing/recent" and get_current_user not in _deps(r.dependant)
    ]
    assert not missing


def test_lists_hide_other_users_objects(client, db, graph, storage):
    assert client.get("/api/collections").json() == []
    assert client.get("/api/queue").json() == []
    trash = client.get("/api/trash").json()
    assert not any(trash.values())

    assert client.delete("/api/trash").status_code == 200
    assert db.get(Series, graph["trashed_series_id"]) is not None
    assert db.get(Image, graph["trashed_image_id"]) is not None
    assert db.get(AIVariant, graph["trashed_variant_id"]) is not None
    storage.delete.assert_not_called()


def _own_series(client):
    return client.post("/api/series", json={"title": "B series"}).json()["id"]


def test_put_series_foreign_collection_404s(client, db, graph):
    sid = _own_series(client)
    resp = client.put(f"/api/series/{sid}", json={"collection_id": graph["collection_id"]})
    assert resp.status_code == 404
    assert db.get(Series, sid).collection_id is None


def test_put_series_foreign_chosen_variant_400s(client, db, graph):
    sid = _own_series(client)
    resp = client.put(f"/api/series/{sid}", json={"chosen_variant_id": graph["variant_id"]})
    assert resp.status_code == 400
    assert db.get(Series, sid).chosen_variant_id is None


def test_patch_frame_foreign_source_image_404s(client, db, graph):
    sid = _own_series(client)
    img = Image(series_id=sid, r2_key="b/img", original_filename="f", order_index=0)
    post = Post(series_id=sid, platform="instagram")
    db.add_all([img, post])
    db.flush()
    story = Story(post_id=post.id)
    db.add(story)
    db.flush()
    frame = StoryFrame(story_id=story.id, position=0, frame_type="text")
    db.add(frame)
    db.commit()
    resp = client.patch(
        f"/api/story-frames/{frame.id}", json={"source_image_id": graph["image_id"]}
    )
    assert resp.status_code == 404
    db.refresh(frame)
    assert frame.source_image_id is None


def test_patch_frame_source_image_from_other_own_series_400s(client, db, graph):
    sid, other_sid = _own_series(client), _own_series(client)
    other_img = Image(series_id=other_sid, r2_key="b/other", original_filename="f", order_index=0)
    post = Post(series_id=sid, platform="instagram")
    db.add_all([other_img, post])
    db.flush()
    story = Story(post_id=post.id)
    db.add(story)
    db.flush()
    frame = StoryFrame(story_id=story.id, position=0, frame_type="text")
    db.add(frame)
    db.commit()
    resp = client.patch(f"/api/story-frames/{frame.id}", json={"source_image_id": other_img.id})
    assert resp.status_code == 400
    db.refresh(frame)
    assert frame.source_image_id is None


def test_move_own_image_into_foreign_series_404s(client, db, graph):
    sid = _own_series(client)
    img = Image(series_id=sid, r2_key="b/img", original_filename="f", order_index=0)
    db.add(img)
    db.commit()
    resp = client.put(f"/api/images/{img.id}/move", json={"target_series_id": graph["series_id"]})
    assert resp.status_code == 404
    db.refresh(img)
    assert img.series_id == sid


# ── folded from test_series_ownership.py ─────────────────────────────────────


def test_list_series_only_shows_own(client, db):
    login_as(client, db, "a@example.com", "g-a")
    client.post("/api/series", json={"title": "A's series"})
    client.cookies.clear()

    login_as(client, db, "b@example.com", "g-b")
    client.post("/api/series", json={"title": "B's series"})

    titles = [s["title"] for s in client.get("/api/series").json()["items"]]
    assert titles == ["B's series"]


def test_get_other_users_series_404s(client, db):
    login_as(client, db, "a@example.com", "g-a")
    sid = client.post("/api/series", json={"title": "A's series"}).json()["id"]
    client.cookies.clear()

    login_as(client, db, "b@example.com", "g-b")
    assert client.get(f"/api/series/{sid}").status_code == 404


def test_delete_other_users_series_404s(client, db):
    login_as(client, db, "a@example.com", "g-a")
    sid = client.post("/api/series", json={"title": "A's series"}).json()["id"]
    client.cookies.clear()

    login_as(client, db, "b@example.com", "g-b")
    assert client.delete(f"/api/series/{sid}").status_code == 404


def test_create_series_sets_owner(client, db):
    user = login_as(client, db)
    sid = client.post("/api/series", json={"title": "Mine"}).json()["id"]
    assert db.get(Series, sid).user_id == user.id
