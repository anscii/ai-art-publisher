import json
import logging
import re
import time
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

import app.database as _db_module
from app.config import get_config
from app.database import get_db
from app.enums import Platform
from app.models import Image, Post, Story, StoryFrame
from app.routers.settings import get_or_create_settings
from app.schemas import (
    StoryCreateRequest,
    StoryFrameResponse,
    StoryFrameUpdate,
    StoryReorderRequest,
    StoryResponse,
    StoryUpdate,
)
from app.services import telegram_stories as tg_stories_svc
from app.services.instagram import InstagramService
from app.services.storage import get_storage_from_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stories"])

_DEFAULT_LINK_AREA: dict = {"x": 75.0, "y": 82.0, "w": 50.0, "h": 10.0}


def get_link_area(story: "Story") -> dict:
    if story.link_area_json:
        try:
            return json.loads(story.link_area_json)
        except (json.JSONDecodeError, ValueError):
            pass
    return _DEFAULT_LINK_AREA


def _parse_link_area(json_str: str | None) -> dict | None:
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────


def split_description(description: str, n: int) -> list[str]:
    """Split description prose into n fragments (paragraph-first, no hashtags)."""
    if not description or n <= 0:
        return []

    text = description
    # Strip "Filed under" section (everything from that line onward)
    text = re.sub(r"\nFiled under:.*", "", text, flags=re.DOTALL).strip()
    # Strip hashtag-only lines
    text = re.sub(r"(?m)^#\w.*$", "", text).strip()
    # Strip inline hashtags
    text = re.sub(r"#\w+", "", text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not text:
        return [""] * n

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return [""] * n

    # Expand: split longest paragraph at sentence boundary until we have n
    while len(paragraphs) < n:
        longest_idx = max(range(len(paragraphs)), key=lambda i: len(paragraphs[i]))
        parts = re.split(r"(?<=[.!?…])\s+", paragraphs[longest_idx], maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            paragraphs[longest_idx : longest_idx + 1] = [p.strip() for p in parts]
        else:
            # Can't split further — pad with empty strings
            paragraphs.extend([""] * (n - len(paragraphs)))
            break

    # Contract: merge tail paragraphs into last slot
    if len(paragraphs) > n:
        tail = "\n\n".join(paragraphs[n - 1 :])
        paragraphs = paragraphs[: n - 1] + [tail]

    return paragraphs


def _split_text_half(text: str) -> tuple[str, str]:
    """Split text into two roughly equal halves at a paragraph or sentence boundary."""
    if not text or not text.strip():
        return ("", "")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) >= 2:
        mid = max(1, len(paragraphs) // 2)
        return ("\n\n".join(paragraphs[:mid]), "\n\n".join(paragraphs[mid:]))

    sentences = re.split(r"(?<=[.!?…])\s+", text.strip())
    if len(sentences) >= 2:
        mid = max(1, len(sentences) // 2)
        return (" ".join(sentences[:mid]), " ".join(sentences[mid:]))

    return (text.strip(), "")


def _story_to_resp(story: Story) -> StoryResponse:
    return StoryResponse(
        id=story.id,
        post_id=story.post_id,
        status=story.status,
        created_at=story.created_at,
        updated_at=story.updated_at,
        rendered_at=story.rendered_at,
        posted_at=story.posted_at,
        error_message=story.error_message,
        link_area=_parse_link_area(story.link_area_json),
        frames=[
            StoryFrameResponse(
                id=f.id,
                story_id=f.story_id,
                position=f.position,
                frame_type=f.frame_type,
                source_image_id=f.source_image_id,
                title=f.title,
                text=f.text,
                is_enabled=f.is_enabled,
                background_mode=f.background_mode,
                text_color=f.text_color,
                text_align=f.text_align,
                title_position=f.title_position,
                text_halign=f.text_halign,
                font_size=f.font_size,
                rendered_url=f.rendered_url,
                platform_frame_id=f.platform_frame_id,
            )
            for f in story.frames
        ],
    )


def _get_story_or_404(story_id: str, db: Session) -> Story:
    story = db.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


def _get_frame_or_404(frame_id: str, db: Session) -> StoryFrame:
    frame = db.get(StoryFrame, frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Story frame not found")
    return frame


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/api/posts/{post_id}/stories", response_model=StoryResponse)
def create_story(post_id: str, body: StoryCreateRequest, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.platform not in (Platform.instagram, Platform.telegram):
        raise HTTPException(
            status_code=400,
            detail="Stories only supported for Instagram and Telegram posts",
        )

    valid_image_ids = {pi.image_id for pi in post.post_images}
    for iid in body.image_ids:
        if iid not in valid_image_ids:
            raise HTTPException(status_code=400, detail=f"Image {iid} not in this post")

    # Replace existing story if any
    if post.story:
        db.delete(post.story)
        db.flush()

    # Preserve post image order, filter to requested selection
    ordered = sorted(post.post_images, key=lambda pi: pi.order_index)
    selected = set(body.image_ids)
    images = [pi.image for pi in ordered if pi.image_id in selected and pi.image is not None]

    fragments = split_description(post.description, len(images))

    now = datetime.now(UTC).replace(tzinfo=None)
    story = Story(post_id=post_id, created_at=now, updated_at=now)
    db.add(story)
    db.flush()

    first_title = (
        (post.title_ru or post.title) if post.platform == Platform.telegram else post.title
    )
    for i, img in enumerate(images):
        db.add(
            StoryFrame(
                story_id=story.id,
                position=i * 2,
                frame_type="image",
                source_image_id=img.id,
                title=first_title if i == 0 else None,
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            StoryFrame(
                story_id=story.id,
                position=i * 2 + 1,
                frame_type="text",
                source_image_id=img.id,
                text=fragments[i] if i < len(fragments) else None,
                created_at=now,
                updated_at=now,
            )
        )

    db.commit()
    db.refresh(story)
    return _story_to_resp(story)


@router.get("/api/stories/{story_id}", response_model=StoryResponse)
def get_story(story_id: str, db: Session = Depends(get_db)):
    return _story_to_resp(_get_story_or_404(story_id, db))


@router.patch("/api/stories/{story_id}", response_model=StoryResponse)
def patch_story(story_id: str, body: StoryUpdate, db: Session = Depends(get_db)):
    story = _get_story_or_404(story_id, db)
    if "link_area" in body.model_fields_set:
        story.link_area_json = json.dumps(body.link_area) if body.link_area else None
    story.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(story)
    return _story_to_resp(story)


@router.patch("/api/story-frames/{frame_id}", response_model=StoryResponse)
def update_frame(frame_id: str, body: StoryFrameUpdate, db: Session = Depends(get_db)):
    frame = _get_frame_or_404(frame_id, db)
    story = frame.story

    content_fields = {
        "text",
        "title",
        "source_image_id",
        "background_mode",
        "text_color",
        "text_align",
        "title_position",
        "text_halign",
        "font_size",
    }
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(frame, field, value)
    content_changed = bool(changes.keys() & content_fields)

    now = datetime.now(UTC).replace(tzinfo=None)
    if content_changed:
        frame.rendered_url = None
        frame.rendered_storage_key = None
        if story.status != "posted":
            story.status = "draft"
        story.updated_at = now

    frame.updated_at = now
    db.commit()
    db.refresh(story)
    return _story_to_resp(story)


@router.post("/api/stories/{story_id}/reorder", response_model=StoryResponse)
def reorder_frames(story_id: str, body: StoryReorderRequest, db: Session = Depends(get_db)):
    story = _get_story_or_404(story_id, db)
    frame_map = {f.id: f for f in story.frames}

    if set(body.frame_ids) != set(frame_map.keys()):
        raise HTTPException(
            status_code=400, detail="frame_ids must contain all frame IDs exactly once"
        )

    for position, frame_id in enumerate(body.frame_ids):
        frame_map[frame_id].position = position

    story.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(story)
    return _story_to_resp(story)


@router.post("/api/stories/{story_id}/frames", response_model=StoryResponse)
def add_text_frame(story_id: str, db: Session = Depends(get_db)):
    story = _get_story_or_404(story_id, db)

    frames_sorted = sorted(story.frames, key=lambda f: f.position)
    last_frame = frames_sorted[-1] if frames_sorted else None

    background_mode = last_frame.background_mode if last_frame else "image_blur_dim"
    source_image_id = last_frame.source_image_id if last_frame else None
    text_color = last_frame.text_color if last_frame else "#ffffff"
    font_size = last_frame.font_size if last_frame else None
    new_position = (last_frame.position + 1) if last_frame else 0

    last_text_frame = next((f for f in reversed(frames_sorted) if f.frame_type == "text"), None)
    new_text: str | None = None
    if last_text_frame and last_text_frame.text:
        first_half, second_half = _split_text_half(last_text_frame.text)
        last_text_frame.text = first_half or None
        last_text_frame.rendered_url = None
        last_text_frame.rendered_storage_key = None
        new_text = second_half or None

    now = datetime.now(UTC).replace(tzinfo=None)
    new_frame = StoryFrame(
        story_id=story.id,
        position=new_position,
        frame_type="text",
        source_image_id=source_image_id,
        background_mode=background_mode,
        text_color=text_color,
        font_size=font_size,
        text=new_text,
        created_at=now,
        updated_at=now,
    )
    db.add(new_frame)

    if story.status != "posted":
        story.status = "draft"
    story.updated_at = now

    db.commit()
    db.refresh(story)
    return _story_to_resp(story)


@router.post("/api/stories/{story_id}/render", response_model=StoryResponse)
def render_story(story_id: str, db: Session = Depends(get_db)):
    from app.services.story_renderer import StoryRenderer

    story = _get_story_or_404(story_id, db)
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)

    enabled_frames = [f for f in story.frames if f.is_enabled]
    if not enabled_frames:
        raise HTTPException(status_code=400, detail="No enabled frames to render")

    # Telegram uses a native MediaAreaUrl link sticker — no need to bake label into JPEG.
    # Instagram has no native link sticker, so render the label for non-Telegram stories.
    is_telegram = story.post.platform == Platform.telegram
    last_text_frame_id: str | None = None
    if not is_telegram:
        for _f in reversed(enabled_frames):
            if _f.frame_type == "text":
                last_text_frame_id = _f.id
                break

    renderer = StoryRenderer()

    # Batch-load all source images in one query (avoids N+1 PK lookups)
    source_ids = {f.source_image_id for f in enabled_frames if f.source_image_id}
    image_by_id: dict[str, Image] = {}
    if source_ids:
        image_by_id = {
            img.id: img for img in db.scalars(select(Image).where(Image.id.in_(source_ids)))
        }

    # Cache downloads by r2_key — paired image/text frames often share one source
    bytes_by_key: dict[str, bytes | None] = {}

    for frame in enabled_frames:
        source_image = image_by_id.get(frame.source_image_id) if frame.source_image_id else None

        image_bytes: bytes | None = None
        if source_image and source_image.r2_key:
            key = source_image.r2_key
            if key not in bytes_by_key:
                try:
                    bytes_by_key[key] = storage.download_bytes(key)
                except Exception as exc:
                    logger.warning("Failed to download source image %s: %s", key, exc)
                    bytes_by_key[key] = None
            image_bytes = bytes_by_key[key]

        try:
            rendered_bytes = renderer.render_frame(
                frame,
                image_bytes,
                is_last_text_frame=(frame.id == last_text_frame_id),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Render failed for frame {frame.id}: {exc}"
            )

        r2_key = f"stories/{story.id}/frame_{frame.id}.jpg"
        storage.upload_bytes(rendered_bytes, r2_key, content_type="image/jpeg")
        frame.rendered_storage_key = r2_key
        # Cache-bust so browser fetches the new JPEG after re-render
        frame.rendered_url = storage.public_url(r2_key) + f"?v={int(time.time())}"

    now = datetime.now(UTC).replace(tzinfo=None)
    story.status = "rendered"
    story.rendered_at = now
    story.updated_at = now
    db.commit()
    db.refresh(story)
    return _story_to_resp(story)


def _run_publish(story_id: str, db: Session) -> None:
    """Core publish loop shared by background task and fake-mode path."""
    story = db.get(Story, story_id)
    if not story:
        return
    settings = get_or_create_settings(db)
    platform = story.post.platform

    enabled_frames = [f for f in story.frames if f.is_enabled]

    fake = get_config().fake_posting
    ig_svc: InstagramService | None = None
    storage = get_storage_from_settings(settings) if not fake else None

    if not fake and platform == Platform.instagram:
        ig_svc = InstagramService(settings.instagram_access_token, settings.instagram_user_id)

    results: list[dict[str, object]] = []

    # Pre-batch Telegram frames in a single MTProto session to avoid N connect/disconnect cycles
    _tg_frame_results: dict[str, dict[str, object]] = {}
    if (
        not fake
        and platform == Platform.telegram
        and storage is not None
        and settings.telegram_api_id
    ):
        tg_frames = [
            f for f in enabled_frames if not f.platform_frame_id and f.rendered_storage_key
        ]
        if tg_frames:
            images = [storage.download_bytes(f.rendered_storage_key or "") for f in tg_frames]
            post_url = story.post.post_url
            # Fallback: reconstruct URL from external_post_id + channel settings if post_url missing
            if not post_url and story.post.external_post_id:
                _ch = (settings.telegram_channel_id or "").strip()
                _mid = story.post.external_post_id
                if _ch.startswith("@"):
                    post_url = f"https://t.me/{_ch.lstrip('@')}/{_mid}"
                elif _ch.startswith("-100"):
                    post_url = f"https://t.me/c/{_ch[4:]}/{_mid}"
            logger.info(
                "TG story publish story=%s post=%s post_url=%r frames=%d",
                story.id,
                story.post_id,
                post_url,
                len(tg_frames),
            )
            area = get_link_area(story)
            last_idx = len(tg_frames) - 1
            link_urls = [post_url if i == last_idx else None for i in range(len(tg_frames))]
            link_areas = [area if i == last_idx else None for i in range(len(tg_frames))]
            batch = tg_stories_svc.post_stories(
                api_id=int(settings.telegram_api_id),
                api_hash=settings.telegram_api_hash,
                session_string=settings.telegram_session_string,
                channel_id=settings.telegram_channel_id,
                images=images,
                link_urls=link_urls,
                link_areas=link_areas,
            )
            _tg_frame_results = dict(zip((f.id for f in tg_frames), batch))

    for idx, frame in enumerate(enabled_frames):
        if not frame.rendered_url:
            story.status = "failed"
            story.error_message = (
                f"Frame {frame.id} has no rendered URL — re-render before publishing"
            )
            story.updated_at = datetime.now(UTC).replace(tzinfo=None)
            db.commit()
            return

        if frame.platform_frame_id:
            result: dict[str, object] = {"ok": True, "id": frame.platform_frame_id}
        elif fake:
            result = {"ok": True, "fake": True, "id": f"fake-story-{frame.id}"}
            logger.info("[FAKE] %s story | story=%s | frame=%s", platform, story.id, frame.id)
        elif platform == Platform.telegram:
            if not frame.rendered_storage_key:
                result = {"ok": False, "description": "No rendered_storage_key for Telegram upload"}
            elif not settings.telegram_api_id:
                result = {"ok": False, "description": "Telegram API ID not configured in settings"}
            else:
                result = _tg_frame_results.get(
                    frame.id,
                    {"ok": False, "description": "Frame missing from Telegram batch results"},
                )
        else:
            assert ig_svc is not None
            result = ig_svc.post_story(frame.rendered_url)

        if not result.get("ok"):
            story.status = "failed"
            story.error_message = str(result.get("description", f"{platform} story post failed"))
            story.updated_at = datetime.now(UTC).replace(tzinfo=None)
            story.platform_result_json = json.dumps(results)
            db.commit()
            return

        _fid = result.get("id") or result.get("media_id") or result.get("story_id")
        frame.platform_frame_id = str(_fid) if _fid is not None else None
        results.append(result)

        if not fake and idx < len(enabled_frames) - 1:
            time.sleep(3)

    now = datetime.now(UTC).replace(tzinfo=None)
    story.status = "posted"
    story.posted_at = now
    story.updated_at = now
    story.error_message = None
    story.platform_result_json = json.dumps(results)
    db.commit()


def _publish_story_background(story_id: str) -> None:
    db = _db_module.SessionLocal()
    try:
        _run_publish(story_id, db)
    except Exception as exc:
        logger.exception("Background story publish failed story=%s: %s", story_id, exc)
        try:
            db.rollback()
            s = db.get(Story, story_id)
            if s and s.status == "publishing":
                s.status = "failed"
                s.error_message = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/api/stories/{story_id}/publish", response_model=StoryResponse)
def publish_story(
    story_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    story = _get_story_or_404(story_id, db)

    enabled_frames = [f for f in story.frames if f.is_enabled]
    if not enabled_frames:
        raise HTTPException(status_code=400, detail="No enabled frames to publish")

    unrendered = [f for f in enabled_frames if not f.rendered_url]
    if unrendered:
        raise HTTPException(
            status_code=400,
            detail=f"{len(unrendered)} frame(s) not yet rendered — call /render first",
        )

    # Atomic update: only transition to "publishing" if not already there or posted.
    # Prevents two concurrent requests from both queuing a background task.
    result = db.execute(
        sa_update(Story)
        .where(Story.id == story_id, Story.status.not_in(["publishing", "posted"]))
        .values(status="publishing", updated_at=datetime.now(UTC).replace(tzinfo=None))
    )
    db.commit()
    if result.rowcount == 0:
        db.refresh(story)
        return _story_to_resp(story)

    db.refresh(story)
    background_tasks.add_task(_publish_story_background, story_id)
    return _story_to_resp(story)
