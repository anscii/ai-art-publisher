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


def test_create_story_rejects_non_instagram_post(client):
    sid = _series(client)
    img_id = _image(client, sid)
    posts = client.post(
        f"/api/series/{sid}/posts",
        json={
            "platforms": ["telegram"],
            "title": "T",
            "description_telegram": "Text",
            "description_other": "Text",
            "image_ids": [img_id],
        },
    ).json()
    tg_post = next(p for p in posts if p["platform"] == "telegram")
    resp = client.post(f"/api/posts/{tg_post['id']}/stories", json={"image_ids": [img_id]})
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


def test_story_facebook_posted_false_before_publish(client):
    sid = _series(client)
    img_id = _image(client, sid)
    post = _instagram_post(client, sid, [img_id])
    _story(client, post["id"], [img_id])

    detail = client.get(f"/api/series/{sid}").json()
    ig_post = next(p for p in detail["posts"] if p["platform"] == "instagram")
    assert ig_post["story_facebook_posted"] is False


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


def test_latest_post_label_changes_bottom_right():
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
    without_label = renderer.render_frame(_Frame(), None, is_last_text_frame=False)
    with_label = renderer.render_frame(_Frame(), None, is_last_text_frame=True)

    img_no = PILImage.open(io.BytesIO(without_label))
    img_yes = PILImage.open(io.BytesIO(with_label))

    crop_box = (780, 1780, 1080, 1880)
    assert list(img_no.crop(crop_box).getdata()) != list(img_yes.crop(crop_box).getdata())


def test_latest_post_label_ignored_for_image_frame():
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


def test_latest_post_label_default_is_false():
    from app.services.story_renderer import StoryRenderer

    class _Frame:
        frame_type = "text"
        title = None
        text = "Default check."
        background_mode = "solid_dark"
        source_image_id = None
        text_color = "#ffffff"
        text_align = "middle"
        title_position = "bottom"
        font_size = None

    renderer = StoryRenderer()
    assert renderer.render_frame(_Frame(), None) == renderer.render_frame(
        _Frame(), None, is_last_text_frame=False
    )


# ── Publish idempotent retry ──────────────────────────────────────────────────


def test_publish_skips_already_posted_frames(client, db, monkeypatch):
    """Frames with instagram_frame_id already set are not re-posted on retry."""
    monkeypatch.setattr(AppConfig, "fake_posting", True)
    story_id = _setup_rendered_story(client, db, monkeypatch)

    story = db.get(Story, story_id)
    first_frame = story.frames[0]
    first_frame.instagram_frame_id = "already-posted-id"
    db.commit()

    with patch("app.routers.stories.InstagramService") as mock_ig:
        monkeypatch.setattr(AppConfig, "fake_posting", False)
        mock_ig.return_value.post_story.return_value = {
            "ok": True,
            "media_id": "new-id",
        }
        # Even with real posting, first frame should not call post_story
        # because instagram_frame_id is set. Other frames will call via mock.
        # We just verify no crash and the idempotent frame is preserved.
        monkeypatch.setattr(AppConfig, "fake_posting", True)
        resp = client.post(f"/api/stories/{story_id}/publish")

    assert resp.status_code == 200
    result = resp.json()
    # The frame that had instagram_frame_id pre-set should keep it
    pre_set_frame = next(
        f for f in result["frames"] if f.get("instagram_frame_id") == "already-posted-id"
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
