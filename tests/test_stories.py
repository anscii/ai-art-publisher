"""Tests for Stories: generation, editing, rendering, publishing."""

import io
from unittest.mock import MagicMock, patch

from PIL import Image as PILImage

from app.config import AppConfig
from app.models import Post, Story
from app.routers.stories import split_description

# ── Helpers ───────────────────────────────────────────────────────────────────


def _series(client, title="Nocturnal Archive"):
    return client.post("/api/series", json={"title": title}).json()["id"]


def _image(client, sid, key="images/test.jpg"):
    return client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": key, "original_filename": "test.jpg"},
    ).json()["id"]


def _instagram_post(client, sid, img_ids, description="Para one.\n\nPara two.", title="Night"):
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["instagram"],
            "title": title,
            "description_telegram": description,
            "description_other": description,
            "image_ids": img_ids,
        },
    ).json()
    return next(p for p in posts if p["platform"] == "instagram")


def _story(client, post_id, image_ids):
    resp = client.post(f"/api/posts/{post_id}/stories", json={"image_ids": image_ids})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fake_jpeg(w=1080, h=1920) -> bytes:
    img = PILImage.new("RGB", (w, h), (100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ── split_description unit tests ──────────────────────────────────────────────


def test_split_description_single_paragraph():
    desc = "He pledged himself to the nocturnal halls."
    result = split_description(desc, 1)
    assert len(result) == 1
    assert result[0] == desc


def test_split_description_two_paragraphs():
    desc = "First paragraph.\n\nSecond paragraph."
    result = split_description(desc, 2)
    assert result == ["First paragraph.", "Second paragraph."]


def test_split_description_strips_hashtags():
    desc = "Clean prose.\n\n#hashtag #art\n\nMore text."
    result = split_description(desc, 2)
    for fragment in result:
        assert "#" not in fragment


def test_split_description_strips_filed_under():
    desc = "Story text.\nFiled under: dark academia\nmore junk"
    result = split_description(desc, 1)
    assert "Filed under" not in result[0]
    assert "dark academia" not in result[0]


def test_split_description_fewer_paragraphs_than_n():
    desc = "Only one paragraph here."
    result = split_description(desc, 2)
    assert len(result) == 2


def test_split_description_more_paragraphs_than_n_merges_tail():
    desc = "P1.\n\nP2.\n\nP3.\n\nP4."
    result = split_description(desc, 2)
    assert len(result) == 2
    assert "P1." in result[0]
    assert "P2." in result[1]
    assert "P3." in result[1]


def test_split_description_empty_returns_empty_strings():
    result = split_description("", 3)
    assert result == []


# ── Story generation ──────────────────────────────────────────────────────────


def test_create_story_1_image(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    data = _story(client, post["id"], [img_id])

    assert data["status"] == "draft"
    frames = data["frames"]
    assert len(frames) == 2
    assert frames[0]["frame_type"] == "image"
    assert frames[1]["frame_type"] == "text"


def test_create_story_first_image_has_title(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id], title="Night Halls")
    data = _story(client, post["id"], [img_id])

    image_frames = [f for f in data["frames"] if f["frame_type"] == "image"]
    assert image_frames[0]["title"] == "Night Halls"


def test_create_story_subsequent_images_have_no_title(client):
    sid = _series(client)
    ids = [_image(client, sid, f"images/img{i}.jpg") for i in range(3)]
    post = _instagram_post(client, sid, ids, title="Night Halls")
    data = _story(client, post["id"], ids)

    image_frames = [f for f in data["frames"] if f["frame_type"] == "image"]
    assert image_frames[0]["title"] == "Night Halls"
    for frame in image_frames[1:]:
        assert frame["title"] is None


def test_create_story_3_images_alternating(client):
    sid = _series(client)
    ids = [_image(client, sid, f"images/img{i}.jpg") for i in range(3)]
    post = _instagram_post(client, sid, ids)
    data = _story(client, post["id"], ids)

    frames = data["frames"]
    assert len(frames) == 6
    types = [f["frame_type"] for f in frames]
    assert types == ["image", "text", "image", "text", "image", "text"]


def test_create_story_no_hashtags_in_text_frames(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id], description="Story text. #art #darkacademia")
    data = _story(client, post["id"], [img_id])

    text_frames = [f for f in data["frames"] if f["frame_type"] == "text"]
    for frame in text_frames:
        if frame["text"]:
            assert "#" not in frame["text"]


def test_create_story_text_background_is_preceding_image(client):
    sid = _series(client)
    ids = [_image(client, sid, f"images/img{i}.jpg") for i in range(2)]
    post = _instagram_post(client, sid, ids)
    data = _story(client, post["id"], ids)

    frames = data["frames"]
    # frame[0]=image(img0), frame[1]=text(bg=img0), frame[2]=image(img1), frame[3]=text(bg=img1)
    assert frames[1]["source_image_id"] == frames[0]["source_image_id"]
    assert frames[3]["source_image_id"] == frames[2]["source_image_id"]


def test_create_story_replaces_existing(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    first = _story(client, post["id"], [img_id])
    second = _story(client, post["id"], [img_id])
    assert first["id"] != second["id"]


def _telegram_post(
    client, sid, img_ids, description="Абзац один.\n\nАбзац два.", title="Ночь", title_ru="Ночь"
):
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram"],
            "title": title,
            "title_ru": title_ru,
            "description_telegram": description,
            "description_other": description,
            "image_ids": img_ids,
        },
    ).json()
    return next(p for p in posts if p["platform"] == "telegram")


def test_create_story_allowed_for_telegram_post(client):
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    resp = client.post(f"/api/posts/{tg_post['id']}/stories", json={"image_ids": [img_id]})
    assert resp.status_code == 200
    assert resp.json()["status"] == "draft"


def test_create_story_telegram_uses_title_ru(client):
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id], title="Night", title_ru="Ночь")
    data = client.post(f"/api/posts/{tg_post['id']}/stories", json={"image_ids": [img_id]}).json()
    image_frame = next(f for f in data["frames"] if f["frame_type"] == "image")
    assert image_frame["title"] == "Ночь"


def test_create_story_allowed_for_instagram_post(client):
    sid = _series(client)
    img_id = _image(client, sid)
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["instagram"],
            "title": "T",
            "description_telegram": "Text",
            "description_other": "Text",
            "image_ids": [img_id],
        },
    ).json()
    ig_post = next(p for p in posts if p["platform"] == "instagram")
    resp = client.post(f"/api/posts/{ig_post['id']}/stories", json={"image_ids": [img_id]})
    assert resp.status_code == 200


def test_create_story_rejects_unsupported_platform(client):
    sid = _series(client)
    img_id = _image(client, sid)
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["facebook"],
            "title": "T",
            "description_telegram": "Text",
            "description_other": "Text",
            "image_ids": [img_id],
        },
    ).json()
    fb_post = next(p for p in posts if p["platform"] == "facebook")
    resp = client.post(f"/api/posts/{fb_post['id']}/stories", json={"image_ids": [img_id]})
    assert resp.status_code == 400


def test_story_id_appears_in_series_detail(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    assert post["story_id"] is None

    _story(client, post["id"], [img_id])

    detail = client.get(f"/api/series/{sid}").json()
    ig_post = next(p for p in detail["posts"] if p["platform"] == "instagram")
    assert ig_post["story_id"] is not None


# ── Frame editing ─────────────────────────────────────────────────────────────


def test_patch_frame_updates_text(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story = _story(client, post["id"], [img_id])

    text_frame = next(f for f in story["frames"] if f["frame_type"] == "text")
    resp = client.patch(f"/api/story-frames/{text_frame['id']}", json={"text": "New text."})
    assert resp.status_code == 200
    updated = resp.json()
    updated_frame = next(f for f in updated["frames"] if f["id"] == text_frame["id"])
    assert updated_frame["text"] == "New text."


def test_patch_frame_text_clears_rendered_url(client, db):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story_data = _story(client, post["id"], [img_id])

    # Manually set rendered_url on a frame and status rendered
    story = db.get(Story, story_data["id"])
    story.status = "rendered"
    text_frame = next(f for f in story.frames if f.frame_type == "text")
    text_frame.rendered_url = "https://r2.example.com/old.jpg"
    db.commit()

    resp = client.patch(f"/api/story-frames/{text_frame.id}", json={"text": "Changed."})
    assert resp.status_code == 200
    result = resp.json()
    updated_frame = next(f for f in result["frames"] if f["id"] == text_frame.id)
    assert updated_frame["rendered_url"] is None
    assert result["status"] == "draft"


def test_patch_frame_is_enabled_does_not_clear_rendered(client, db):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story_data = _story(client, post["id"], [img_id])

    story = db.get(Story, story_data["id"])
    story.status = "rendered"
    text_frame = next(f for f in story.frames if f.frame_type == "text")
    text_frame.rendered_url = "https://r2.example.com/existing.jpg"
    db.commit()

    resp = client.patch(f"/api/story-frames/{text_frame.id}", json={"is_enabled": False})
    assert resp.status_code == 200
    result = resp.json()
    updated_frame = next(f for f in result["frames"] if f["id"] == text_frame.id)
    assert updated_frame["rendered_url"] == "https://r2.example.com/existing.jpg"


# ── Reorder ───────────────────────────────────────────────────────────────────


def test_reorder_frames(client):
    sid = _series(client)
    ids = [_image(client, sid, f"images/img{i}.jpg") for i in range(2)]
    post = _instagram_post(client, sid, ids)
    story = _story(client, post["id"], ids)

    frame_ids = [f["id"] for f in story["frames"]]
    reversed_ids = list(reversed(frame_ids))

    resp = client.post(f"/api/stories/{story['id']}/reorder", json={"frame_ids": reversed_ids})
    assert resp.status_code == 200
    reordered = resp.json()
    assert [f["id"] for f in reordered["frames"]] == reversed_ids


def test_reorder_rejects_wrong_frame_count(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story = _story(client, post["id"], [img_id])

    resp = client.post(f"/api/stories/{story['id']}/reorder", json={"frame_ids": ["nonexistent"]})
    assert resp.status_code == 400


# ── Rendering ─────────────────────────────────────────────────────────────────


def test_render_story_produces_rendered_urls(client, monkeypatch):
    monkeypatch.setattr(AppConfig, "local_storage", True)
    monkeypatch.setattr(AppConfig, "data_dir", "/tmp/test_stories_render")

    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story = _story(client, post["id"], [img_id])

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = _fake_jpeg()
    mock_storage.upload_bytes.return_value = "stories/test/frame.jpg"
    mock_storage.public_url.side_effect = lambda k: f"/uploads/{k}"

    with patch("app.routers.stories.get_storage_from_settings", return_value=mock_storage):
        resp = client.post(f"/api/stories/{story['id']}/render")

    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "rendered"
    for frame in result["frames"]:
        if frame["is_enabled"]:
            assert frame["rendered_url"] is not None


def test_latest_post_label_renders_on_last_text_frame():
    """Renderer draws "↘ latest post" label when is_last_text_frame=True."""
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Closing thought."
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        font_size = None

    renderer = StoryRenderer()
    without = renderer.render_frame(_Frame(), None, is_last_text_frame=False)
    with_label = renderer.render_frame(_Frame(), None, is_last_text_frame=True)

    crop = (780, 1780, 1080, 1880)
    assert list(PILImage.open(io.BytesIO(without)).crop(crop).getdata()) != list(
        PILImage.open(io.BytesIO(with_label)).crop(crop).getdata()
    )


def test_latest_post_label_not_drawn_on_image_frame():
    """Image frames never get the label regardless of is_last_text_frame."""
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "image"
        title = None
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        font_size = None
        background_mode = "solid_dark"

    renderer = StoryRenderer()
    assert renderer.render_frame(_Frame(), None, is_last_text_frame=False) == renderer.render_frame(
        _Frame(), None, is_last_text_frame=True
    )


def test_render_instagram_story_passes_label_flag_for_last_text_frame(client, monkeypatch):
    """render endpoint passes is_last_text_frame=True only for last text frame of Instagram story."""
    from app.services.story_renderer import StoryRenderer

    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story_data = _story(client, post["id"], [img_id])

    calls: list[dict] = []
    real_render = StoryRenderer.render_frame

    def spy_render(self, frame, image_bytes, *, is_last_text_frame=False):
        calls.append({"frame_type": frame.frame_type, "is_last": is_last_text_frame})
        return real_render(self, frame, image_bytes, is_last_text_frame=is_last_text_frame)

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = _fake_jpeg()
    mock_storage.upload_bytes.return_value = "stories/test/frame.jpg"
    mock_storage.public_url.side_effect = lambda k: f"/uploads/{k}"

    with (
        patch("app.routers.stories.get_storage_from_settings", return_value=mock_storage),
        patch.object(StoryRenderer, "render_frame", spy_render),
    ):
        resp = client.post(f"/api/stories/{story_data['id']}/render")

    assert resp.status_code == 200
    text_calls = [c for c in calls if c["frame_type"] == "text"]
    assert text_calls, "expected at least one text frame"
    # Exactly the last text frame should have is_last_text_frame=True
    assert text_calls[-1]["is_last"] is True
    assert all(not c["is_last"] for c in text_calls[:-1])


def test_render_telegram_story_never_passes_label_flag(client, monkeypatch):
    """render endpoint always passes is_last_text_frame=False for Telegram stories."""
    from app.services.story_renderer import StoryRenderer

    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story_data = _story(client, tg_post["id"], [img_id])

    calls: list[dict] = []
    real_render = StoryRenderer.render_frame

    def spy_render(self, frame, image_bytes, *, is_last_text_frame=False):
        calls.append({"frame_type": frame.frame_type, "is_last": is_last_text_frame})
        return real_render(self, frame, image_bytes, is_last_text_frame=is_last_text_frame)

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = _fake_jpeg()
    mock_storage.upload_bytes.return_value = "stories/test/frame.jpg"
    mock_storage.public_url.side_effect = lambda k: f"/uploads/{k}"

    with (
        patch("app.routers.stories.get_storage_from_settings", return_value=mock_storage),
        patch.object(StoryRenderer, "render_frame", spy_render),
    ):
        resp = client.post(f"/api/stories/{story_data['id']}/render")

    assert resp.status_code == 200
    assert calls, "expected at least one frame rendered"
    assert all(not c["is_last"] for c in calls), "Telegram frames must never get the label"


def test_render_produces_1080x1920_jpeg(monkeypatch):
    """Unit test: renderer output is a valid 1080x1920 JPEG."""
    from app.services.story_renderer import StoryRenderer

    class _FakeFrame:
        frame_type = "text"
        title = None
        text = "He pledged himself\nto the nocturnal halls."
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        font_size = None

    renderer = StoryRenderer()
    result = renderer.render_frame(_FakeFrame(), None)

    img = PILImage.open(io.BytesIO(result))
    assert img.size == (1080, 1920)
    assert img.format == "JPEG"


def test_render_image_frame_produces_correct_size(monkeypatch):
    from app.services.story_renderer import StoryRenderer

    class _FakeFrame:
        frame_type = "image"
        title = "Night Halls"
        source_image_id = "abc"
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        font_size = None
        background_mode = "solid_dark"

    renderer = StoryRenderer()
    result = renderer.render_frame(_FakeFrame(), _fake_jpeg(800, 600))

    img = PILImage.open(io.BytesIO(result))
    assert img.size == (1080, 1920)


# ── Publishing ────────────────────────────────────────────────────────────────


def _setup_rendered_story(client, db, monkeypatch):
    """Create a story with all frames pre-marked as rendered."""
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story_data = _story(client, post["id"], [img_id])

    story = db.get(Story, story_data["id"])
    for frame in story.frames:
        frame.rendered_url = f"https://r2.example.com/frame_{frame.id}.jpg"
    story.status = "rendered"
    db.commit()
    return story_data["id"]


def test_fake_publish_sets_posted(client, db, monkeypatch):
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    story_id = _setup_rendered_story(client, db, monkeypatch)
    resp = client.post(f"/api/stories/{story_id}/publish")
    assert resp.status_code == 200
    # Endpoint returns immediately with "publishing"; background task runs
    # synchronously in TestClient so final DB state should be "posted".
    assert resp.json()["status"] == "publishing"
    db.expire_all()
    story = db.get(Story, story_id)
    assert story.status == "posted"


def test_fake_publish_no_real_api_called(client, db, monkeypatch):
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    story_id = _setup_rendered_story(client, db, monkeypatch)

    with patch("app.routers.stories.InstagramService") as mock_ig:
        client.post(f"/api/stories/{story_id}/publish")
        mock_ig.assert_not_called()


def test_publish_requires_rendered_frames(client, db, monkeypatch):
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story = _story(client, post["id"], [img_id])
    # No frames rendered
    resp = client.post(f"/api/stories/{story['id']}/publish")
    assert resp.status_code == 400


def test_story_not_stored_as_separate_post(client, db, monkeypatch):
    """Publishing a story must not create a new Post entity."""
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    before_count = db.query(Post).count()
    story_data = _story(client, post["id"], [img_id])

    story = db.get(Story, story_data["id"])
    for frame in story.frames:
        frame.rendered_url = "https://r2.example.com/frame.jpg"
    story.status = "rendered"
    db.commit()

    client.post(f"/api/stories/{story_data['id']}/publish")
    after_count = db.query(Post).count()
    assert after_count == before_count


# ── story_status in PostResponse ──────────────────────────────────────────────


def test_story_status_in_post_response(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    assert post["story_status"] is None

    _story(client, post["id"], [img_id])

    detail = client.get(f"/api/series/{sid}").json()
    ig_post = next(p for p in detail["posts"] if p["platform"] == "instagram")
    assert ig_post["story_status"] == "draft"


def test_story_frame_count_in_post_response(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])

    # No story yet
    assert post["story_frame_count"] is None

    # Story with 1 image → 2 frames (image + text)
    _story(client, post["id"], [img_id])
    detail = client.get(f"/api/series/{sid}").json()
    ig_post = next(p for p in detail["posts"] if p["platform"] == "instagram")
    assert ig_post["story_frame_count"] == 2


def test_fake_publish_telegram_story(client, db, monkeypatch):
    """Telegram story publish in fake mode sets status=posted without calling Telethon."""
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story_data = _story(client, tg_post["id"], [img_id])

    story = db.get(Story, story_data["id"])
    for frame in story.frames:
        frame.rendered_url = f"https://r2.example.com/frame_{frame.id}.jpg"
        frame.rendered_storage_key = f"stories/test/frame_{frame.id}.jpg"
    story.status = "rendered"
    db.commit()

    with patch("app.routers.stories.tg_stories_svc") as mock_tg:
        resp = client.post(f"/api/stories/{story_data['id']}/publish")
        mock_tg.post_stories.assert_not_called()

    assert resp.status_code == 200
    db.expire_all()
    story = db.get(Story, story_data["id"])
    assert story.status == "posted"


# ── GET story ─────────────────────────────────────────────────────────────────


def test_get_story(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    created = _story(client, post["id"], [img_id])

    resp = client.get(f"/api/stories/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]
    assert resp.json()["post_id"] == post["id"]


def test_get_story_404(client):
    resp = client.get("/api/stories/nonexistent-id")
    assert resp.status_code == 404


# ── create_story validation ───────────────────────────────────────────────────


def test_create_story_rejects_image_not_in_post(client):
    sid = _series(client)
    img_id = _image(client, sid)
    other_img = _image(client, sid, key="images/other.jpg")
    post = _instagram_post(client, sid, [img_id])
    resp = client.post(f"/api/posts/{post['id']}/stories", json={"image_ids": [other_img]})
    assert resp.status_code == 400


# ── PATCH: new style fields clear rendered_url ────────────────────────────────


def test_patch_frame_style_fields_clear_rendered(client, db):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story_data = _story(client, post["id"], [img_id])

    story = db.get(Story, story_data["id"])
    text_frame = next(f for f in story.frames if f.frame_type == "text")
    text_frame.rendered_url = "https://r2.example.com/old.jpg"
    story.status = "rendered"
    db.commit()

    for field, value in [
        ("text_color", "#0e0e10"),
        ("text_align", "top"),
        ("font_size", 80),
        ("text_halign", "left"),
    ]:
        # Re-set rendered URL before each patch
        text_frame.rendered_url = "https://r2.example.com/old.jpg"
        story.status = "rendered"
        db.commit()

        resp = client.patch(f"/api/story-frames/{text_frame.id}", json={field: value})
        assert resp.status_code == 200, f"PATCH {field} failed"
        result = resp.json()
        frame_data = next(f for f in result["frames"] if f["id"] == text_frame.id)
        assert frame_data["rendered_url"] is None, f"{field} did not clear rendered_url"
        assert result["status"] == "draft", f"{field} did not reset status to draft"


# ── Renderer: style fields applied ────────────────────────────────────────────


def test_renderer_respects_text_color():
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Test"
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#0e0e10"  # ink / near-black
        text_align = "middle"
        title_position = "bottom"
        font_size = None

    renderer = StoryRenderer()
    result = renderer.render_frame(_Frame(), None)
    img = PILImage.open(io.BytesIO(result))
    assert img.size == (1080, 1920)


def test_renderer_respects_text_align_top():
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Top aligned text"
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "top"
        title_position = "bottom"
        font_size = None

    renderer = StoryRenderer()
    result = renderer.render_frame(_Frame(), None)
    img = PILImage.open(io.BytesIO(result))
    assert img.size == (1080, 1920)


def test_renderer_respects_font_size():
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Big text"
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        font_size = 96

    renderer = StoryRenderer()
    result = renderer.render_frame(_Frame(), None)
    img = PILImage.open(io.BytesIO(result))
    assert img.size == (1080, 1920)


def test_renderer_respects_text_halign_left():
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Left aligned"
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        text_halign = "left"
        font_size = None

    renderer = StoryRenderer()
    result = renderer.render_frame(_Frame(), None)
    img = PILImage.open(io.BytesIO(result))
    assert img.size == (1080, 1920)


def test_renderer_respects_text_halign_right():
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Right aligned"
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        text_halign = "right"
        font_size = None

    renderer = StoryRenderer()
    result = renderer.render_frame(_Frame(), None)
    img = PILImage.open(io.BytesIO(result))
    assert img.size == (1080, 1920)


def test_renderer_solid_accent_background():
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Accent bg"
        background_mode = "solid_accent"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        font_size = None

    renderer = StoryRenderer()
    result = renderer.render_frame(_Frame(), None)
    img = PILImage.open(io.BytesIO(result))
    # Dominant color should be accent orange (184, 80, 31)
    pixels = list(img.getdata())
    r_avg = sum(p[0] for p in pixels) / len(pixels)
    assert r_avg > 100  # orange-dominant (red channel high)


# ── Publish idempotent retry ──────────────────────────────────────────────────


def test_publish_skips_already_posted_frames(client, db, monkeypatch):
    """Frames with platform_frame_id already set are not re-posted on retry."""
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    story_id = _setup_rendered_story(client, db, monkeypatch)

    story = db.get(Story, story_id)
    first_frame = story.frames[0]
    first_frame.platform_frame_id = "already-posted-id"
    db.commit()

    with patch("app.routers.stories.InstagramService") as mock_ig:
        monkeypatch.setattr(AppConfig, "fake_posting", False)
        mock_ig.return_value.post_story.return_value = {
            "ok": True,
            "media_id": "new-id",
        }
        monkeypatch.setattr(AppConfig, "fake_posting", True)
        resp = client.post(f"/api/stories/{story_id}/publish")

    assert resp.status_code == 200
    result = resp.json()
    pre_set_frame = next(
        f for f in result["frames"] if f.get("platform_frame_id") == "already-posted-id"
    )
    assert pre_set_frame is not None


# ── add_text_frame endpoint ───────────────────────────────────────────────────


def test_add_text_frame_appends_frame(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story = _story(client, post["id"], [img_id])
    story_id = story["id"]
    original_count = len(story["frames"])

    resp = client.post(f"/api/stories/{story_id}/frames")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["frames"]) == original_count + 1
    new_frame = data["frames"][-1]
    assert new_frame["frame_type"] == "text"
    assert new_frame["position"] == max(f["position"] for f in story["frames"]) + 1


def test_add_text_frame_inherits_background(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story = _story(client, post["id"], [img_id])
    story_id = story["id"]
    last_frame = story["frames"][-1]

    resp = client.post(f"/api/stories/{story_id}/frames")
    assert resp.status_code == 200
    new_frame = resp.json()["frames"][-1]
    assert new_frame["background_mode"] == last_frame["background_mode"]
    assert new_frame["source_image_id"] == last_frame["source_image_id"]


def test_add_text_frame_splits_last_text_frame(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(
        client, sid, [img_id], description="First sentence here. Second sentence here."
    )
    story = _story(client, post["id"], [img_id])
    story_id = story["id"]
    last_text_before = next(f for f in reversed(story["frames"]) if f["frame_type"] == "text")
    original_text = last_text_before["text"] or ""

    resp = client.post(f"/api/stories/{story_id}/frames")
    assert resp.status_code == 200
    frames = resp.json()["frames"]
    updated_last_text = next(f for f in frames if f["id"] == last_text_before["id"])
    new_frame = frames[-1]

    # original text is split: neither part equals original, and together they cover it
    assert updated_last_text["text"] != original_text
    combined = (updated_last_text["text"] or "") + " " + (new_frame["text"] or "")
    for word in original_text.split():
        assert word in combined


def test_add_text_frame_inherits_text_format(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    story = _story(client, post["id"], [img_id])
    story_id = story["id"]

    # Set a distinctive font_size and text_color on the last frame before adding
    last_frame_id = story["frames"][-1]["id"]
    client.patch(
        f"/api/story-frames/{last_frame_id}", json={"font_size": 48, "text_color": "#b8501f"}
    )

    resp = client.post(f"/api/stories/{story_id}/frames")
    assert resp.status_code == 200
    new_frame = resp.json()["frames"][-1]
    assert new_frame["font_size"] == 48
    assert new_frame["text_color"] == "#b8501f"


def test_add_text_frame_404_on_unknown_story(client):
    resp = client.post("/api/stories/nonexistent-id/frames")
    assert resp.status_code == 404


# ── telegram_stories service unit tests ──────────────────────────────────────


def test_telegram_stories_post_stories_calls_telethon():
    """post_stories passes args to _post_stories_async via asyncio.run."""
    from unittest.mock import MagicMock, patch

    mock_results = [{"ok": True, "story_id": 42}, {"ok": True, "story_id": 43}]
    fake_coro = MagicMock(name="coro")

    with (
        patch(
            "app.services.telegram_stories._post_stories_async",
            new=MagicMock(return_value=fake_coro),
        ) as mock_fn,
        patch("app.services.telegram_stories.asyncio") as mock_asyncio,
    ):
        mock_asyncio.run.return_value = mock_results
        from app.services.telegram_stories import post_stories

        result = post_stories(
            api_id=12345,
            api_hash="abc",
            session_string="session",
            channel_id="@mychannel",
            images=[b"fake1", b"fake2"],
        )

    assert result == mock_results
    mock_fn.assert_called_once_with(
        12345, "abc", "session", "@mychannel", [b"fake1", b"fake2"], None, None
    )
    mock_asyncio.run.assert_called_once_with(fake_coro)


# ── story link area (PATCH /api/stories/{id}) ─────────────────────────────────


def test_story_patch_link_area(client):
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story = _story(client, tg_post["id"], [img_id])

    area = {"x": 60.0, "y": 80.0, "w": 40.0, "h": 8.0}
    resp = client.patch(f"/api/stories/{story['id']}", json={"link_area": area})
    assert resp.status_code == 200
    assert resp.json()["link_area"] == area


def test_story_patch_link_area_clear(client):
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story = _story(client, tg_post["id"], [img_id])

    # Set then clear
    client.patch(
        f"/api/stories/{story['id']}", json={"link_area": {"x": 50, "y": 50, "w": 40, "h": 8}}
    )
    resp = client.patch(f"/api/stories/{story['id']}", json={"link_area": None})
    assert resp.status_code == 200
    assert resp.json()["link_area"] is None


def test_story_patch_link_area_404(client):
    resp = client.patch(
        "/api/stories/nonexistent", json={"link_area": {"x": 50, "y": 50, "w": 40, "h": 8}}
    )
    assert resp.status_code == 404


def test_tg_story_publish_passes_link_to_last_frame(client, db, monkeypatch):
    """publish calls post_stories with post_url on last frame, None on others."""
    from app.config import AppConfig
    from app.models import Story

    monkeypatch.setattr(AppConfig, "fake_posting", False)
    sid = _series(client)
    img_id1 = _image(client, sid, key="images/a.jpg")
    img_id2 = _image(client, sid, key="images/b.jpg")
    tg_post = _telegram_post(client, sid, [img_id1, img_id2])

    # Set post_url on the post so the link sticker is active
    post_obj = db.get(Post, tg_post["id"])
    post_obj.post_url = "https://t.me/murky_airt/42"
    db.commit()

    story_data = _story(client, tg_post["id"], [img_id1, img_id2])
    story = db.get(Story, story_data["id"])
    for frame in story.frames:
        frame.rendered_url = f"https://r2.example.com/frame_{frame.id}.jpg"
        frame.rendered_storage_key = f"stories/test/frame_{frame.id}.jpg"
    story.status = "rendered"
    db.commit()

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = _fake_jpeg()

    captured = {}

    def fake_post_stories(**kwargs):
        captured.update(kwargs)
        return [{"ok": True, "story_id": i} for i in range(len(kwargs["images"]))]

    with (
        patch("app.routers.stories.get_storage_from_settings", return_value=mock_storage),
        patch("app.routers.stories.tg_stories_svc") as mock_tg,
    ):
        mock_tg.post_stories.side_effect = fake_post_stories
        monkeypatch.setattr(AppConfig, "fake_posting", False)

        # Patch settings so we have api credentials
        from app.routers.settings import get_or_create_settings

        db.expire_all()
        settings = get_or_create_settings(db)
        settings.telegram_api_id = "12345"
        settings.telegram_api_hash = "abc"
        settings.telegram_session_string = "sess"
        settings.telegram_channel_id = "@chan"
        db.commit()

        resp = client.post(f"/api/stories/{story_data['id']}/publish")

    assert resp.status_code == 200
    link_urls = captured.get("link_urls", [])
    assert link_urls[-1] == "https://t.me/murky_airt/42"
    assert all(u is None for u in link_urls[:-1])


def test_tg_story_publish_link_on_retry_last_frame_only_unposted(client, db, monkeypatch):
    """Retry publish: first frame already posted, sole remaining frame still gets link_url."""
    monkeypatch.setattr(AppConfig, "fake_posting", False)
    sid = _series(client)
    img_id1 = _image(client, sid, key="images/a.jpg")
    img_id2 = _image(client, sid, key="images/b.jpg")
    tg_post = _telegram_post(client, sid, [img_id1, img_id2])

    post_obj = db.get(Post, tg_post["id"])
    post_obj.post_url = "https://t.me/murky_airt/55"
    db.commit()

    story_data = _story(client, tg_post["id"], [img_id1, img_id2])
    story = db.get(Story, story_data["id"])

    # Simulate all but last frame already posted (partial post from yesterday)
    for frame in story.frames[:-1]:
        frame.platform_frame_id = "prev-posted-id"
    for frame in story.frames:
        frame.rendered_url = f"https://r2.example.com/frame_{frame.id}.jpg"
        frame.rendered_storage_key = f"stories/test/frame_{frame.id}.jpg"
    story.status = "rendered"
    db.commit()

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = _fake_jpeg()

    captured = {}

    def fake_post_stories(**kwargs):
        captured.update(kwargs)
        return [{"ok": True, "story_id": i} for i in range(len(kwargs["images"]))]

    with (
        patch("app.routers.stories.get_storage_from_settings", return_value=mock_storage),
        patch("app.routers.stories.tg_stories_svc") as mock_tg,
    ):
        mock_tg.post_stories.side_effect = fake_post_stories
        from app.routers.settings import get_or_create_settings

        db.expire_all()
        settings = get_or_create_settings(db)
        settings.telegram_api_id = "12345"
        settings.telegram_api_hash = "abc"
        settings.telegram_session_string = "sess"
        settings.telegram_channel_id = "@chan"
        db.commit()

        resp = client.post(f"/api/stories/{story_data['id']}/publish")

    assert resp.status_code == 200
    # Only the unposted second frame should have been submitted
    assert len(captured.get("images", [])) == 1
    link_urls = captured.get("link_urls", [])
    assert link_urls == ["https://t.me/murky_airt/55"]


def test_tg_story_publish_link_reconstructed_from_external_post_id(client, db, monkeypatch):
    """publish reconstructs post_url from external_post_id when post_url is null."""
    monkeypatch.setattr(AppConfig, "fake_posting", False)
    sid = _series(client)
    img_id = _image(client, sid, key="images/a.jpg")
    tg_post = _telegram_post(client, sid, [img_id])

    post_obj = db.get(Post, tg_post["id"])
    post_obj.post_url = None
    post_obj.external_post_id = "77"
    db.commit()

    story_data = _story(client, tg_post["id"], [img_id])
    story = db.get(Story, story_data["id"])
    for frame in story.frames:
        frame.rendered_url = f"https://r2.example.com/frame_{frame.id}.jpg"
        frame.rendered_storage_key = f"stories/test/frame_{frame.id}.jpg"
    story.status = "rendered"
    db.commit()

    mock_storage = MagicMock()
    mock_storage.download_bytes.return_value = _fake_jpeg()

    captured = {}

    def fake_post_stories(**kwargs):
        captured.update(kwargs)
        return [{"ok": True, "story_id": i} for i in range(len(kwargs["images"]))]

    with (
        patch("app.routers.stories.get_storage_from_settings", return_value=mock_storage),
        patch("app.routers.stories.tg_stories_svc") as mock_tg,
    ):
        mock_tg.post_stories.side_effect = fake_post_stories
        from app.routers.settings import get_or_create_settings

        db.expire_all()
        settings = get_or_create_settings(db)
        settings.telegram_api_id = "12345"
        settings.telegram_api_hash = "abc"
        settings.telegram_session_string = "sess"
        settings.telegram_channel_id = "-1001234567890"
        db.commit()

        resp = client.post(f"/api/stories/{story_data['id']}/publish")

    assert resp.status_code == 200
    link_urls = captured.get("link_urls", [])
    assert link_urls[-1] == "https://t.me/c/1234567890/77"


def test_tg_story_publish_no_link_when_no_post_url(client, db, monkeypatch):
    """publish sends no link when post has no post_url."""
    from app.config import AppConfig
    from app.models import Story

    monkeypatch.setattr(AppConfig, "fake_posting", True)
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story_data = _story(client, tg_post["id"], [img_id])

    story = db.get(Story, story_data["id"])
    for frame in story.frames:
        frame.rendered_url = f"https://r2.example.com/frame_{frame.id}.jpg"
        frame.rendered_storage_key = f"stories/test/frame_{frame.id}.jpg"
    story.status = "rendered"
    db.commit()

    with patch("app.routers.stories.tg_stories_svc") as mock_tg:
        resp = client.post(f"/api/stories/{story_data['id']}/publish")
        mock_tg.post_stories.assert_not_called()  # fake_posting = True

    assert resp.status_code == 200


# ── link_area validation & resilience ────────────────────────────────────────


def test_story_patch_link_area_rejects_partial_dict(client):
    """PATCH with missing required keys returns 422."""
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story = _story(client, tg_post["id"], [img_id])

    resp = client.patch(f"/api/stories/{story['id']}", json={"link_area": {"x": 50}})
    assert resp.status_code == 422


def test_story_patch_link_area_rejects_non_numeric(client):
    """PATCH with non-numeric coordinate returns 422."""
    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story = _story(client, tg_post["id"], [img_id])

    resp = client.patch(
        f"/api/stories/{story['id']}",
        json={"link_area": {"x": "bad", "y": 80, "w": 50, "h": 10}},
    )
    assert resp.status_code == 422


def test_story_get_survives_malformed_link_area_json(client, db):
    """GET returns link_area=None (not 500) when stored JSON is corrupt."""
    from app.models import Story

    sid = _series(client)
    img_id = _image(client, sid)
    tg_post = _telegram_post(client, sid, [img_id])
    story_data = _story(client, tg_post["id"], [img_id])

    story = db.get(Story, story_data["id"])
    story.link_area_json = "{bad json"
    db.commit()

    resp = client.get(f"/api/stories/{story_data['id']}")
    assert resp.status_code == 200
    assert resp.json()["link_area"] is None


def test_get_link_area_survives_malformed_json():
    """get_link_area falls back to defaults on corrupt stored JSON."""
    from app.routers.stories import _DEFAULT_LINK_AREA, get_link_area

    class _Stub:
        link_area_json = "{corrupt"

    assert get_link_area(_Stub()) == _DEFAULT_LINK_AREA


def test_draw_link_button_returns_valid_jpeg():
    """draw_link_button composites a pill onto the image and returns a valid JPEG."""
    from app.services.story_renderer import draw_link_button

    # Create a minimal 1080×1920 white JPEG
    buf = io.BytesIO()
    PILImage.new("RGB", (1080, 1920), (200, 200, 200)).save(buf, "JPEG")
    original_bytes = buf.getvalue()

    area = {"x": 75.0, "y": 82.0, "w": 50.0, "h": 10.0}
    result = draw_link_button(original_bytes, area)

    # Must be valid JPEG of same dimensions
    assert isinstance(result, bytes)
    out = PILImage.open(io.BytesIO(result))
    assert out.format == "JPEG"
    assert out.size == (1080, 1920)
    # Must differ from original (pill was composited)
    assert result != original_bytes


def test_draw_link_button_custom_label():
    """draw_link_button accepts a custom label without error."""
    from app.services.story_renderer import draw_link_button

    buf = io.BytesIO()
    PILImage.new("RGB", (540, 960), (100, 100, 100)).save(buf, "JPEG")

    result = draw_link_button(
        buf.getvalue(), {"x": 50.0, "y": 50.0, "w": 40.0, "h": 8.0}, label="↗ view post"
    )
    out = PILImage.open(io.BytesIO(result))
    assert out.size == (540, 960)
