import json
import logging
import re
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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
)
from app.services.facebook import FacebookService
from app.services.instagram import InstagramService
from app.services.storage import get_storage_from_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stories"])


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
                font_size=f.font_size,
                rendered_url=f.rendered_url,
                instagram_frame_id=f.instagram_frame_id,
                facebook_frame_id=f.facebook_frame_id,
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
    if post.platform != Platform.instagram:
        raise HTTPException(status_code=400, detail="Stories only supported for Instagram posts")

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

    position = 0
    for i, img in enumerate(images):
        db.add(
            StoryFrame(
                story_id=story.id,
                position=position,
                frame_type="image",
                source_image_id=img.id,
                title=post.title if i == 0 else None,
                created_at=now,
                updated_at=now,
            )
        )
        position += 1
        db.add(
            StoryFrame(
                story_id=story.id,
                position=position,
                frame_type="text",
                source_image_id=img.id,
                text=fragments[i] if i < len(fragments) else None,
                created_at=now,
                updated_at=now,
            )
        )
        position += 1

    db.commit()
    db.refresh(story)
    return _story_to_resp(story)


@router.get("/api/stories/{story_id}", response_model=StoryResponse)
def get_story(story_id: str, db: Session = Depends(get_db)):
    return _story_to_resp(_get_story_or_404(story_id, db))


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
        "font_size",
    }
    content_changed = False

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(frame, field, value)
        if field in content_fields:
            content_changed = True

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


@router.post("/api/stories/{story_id}/render", response_model=StoryResponse)
def render_story(story_id: str, db: Session = Depends(get_db)):
    from app.services.story_renderer import StoryRenderer

    story = _get_story_or_404(story_id, db)
    settings = get_or_create_settings(db)
    storage = get_storage_from_settings(settings)

    enabled_frames = [f for f in story.frames if f.is_enabled]
    if not enabled_frames:
        raise HTTPException(status_code=400, detail="No enabled frames to render")

    renderer = StoryRenderer()

    for frame in enabled_frames:
        source_image: Image | None = None
        if frame.source_image_id:
            source_image = db.get(Image, frame.source_image_id)

        image_bytes: bytes | None = None
        if source_image and source_image.r2_key:
            try:
                image_bytes = storage.download_bytes(source_image.r2_key)
            except Exception as exc:
                logger.warning("Failed to download source image %s: %s", source_image.r2_key, exc)

        try:
            rendered_bytes = renderer.render_frame(frame, image_bytes)
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


@router.post("/api/stories/{story_id}/publish", response_model=StoryResponse)
def publish_story(story_id: str, db: Session = Depends(get_db)):
    story = _get_story_or_404(story_id, db)
    settings = get_or_create_settings(db)

    enabled_frames = [f for f in story.frames if f.is_enabled]
    if not enabled_frames:
        raise HTTPException(status_code=400, detail="No enabled frames to publish")

    unrendered = [f for f in enabled_frames if not f.rendered_url]
    if unrendered:
        raise HTTPException(
            status_code=400,
            detail=f"{len(unrendered)} frame(s) not yet rendered — call /render first",
        )

    fake = get_config().fake_posting
    ig_svc: InstagramService | None = None
    fb_svc: FacebookService | None = None

    if not fake:
        ig_svc = InstagramService(settings.instagram_access_token, settings.instagram_user_id)
        if settings.facebook_page_id:
            fb_svc = FacebookService(settings.facebook_page_access_token, settings.facebook_page_id)

    ig_results: list[dict[str, object]] = []
    fb_results: list[dict[str, object]] = []

    for frame in enabled_frames:
        rendered_url: str = frame.rendered_url  # type: ignore[assignment]

        # Instagram — skip frames already posted (idempotent retry)
        if frame.instagram_frame_id:
            ig_result: dict[str, object] = {"ok": True, "media_id": frame.instagram_frame_id}
        elif fake:
            ig_result = {
                "ok": True,
                "fake": True,
                "media_id": f"fake-story-{frame.id}",
            }
            logger.info("[FAKE] Instagram story | story=%s | frame=%s", story.id, frame.id)
        else:
            assert ig_svc is not None
            ig_result = ig_svc.post_story(rendered_url)

        if not ig_result.get("ok"):
            story.status = "failed"
            story.error_message = str(ig_result.get("description", "Instagram story post failed"))
            story.updated_at = datetime.now(UTC).replace(tzinfo=None)
            story.instagram_result_json = json.dumps(ig_results)
            db.commit()
            raise HTTPException(status_code=502, detail=story.error_message)

        frame.instagram_frame_id = str(ig_result["media_id"]) if ig_result.get("media_id") else None
        ig_results.append(ig_result)

        # Facebook (mirror behavior: attempt if configured, silently skip if not)
        if fb_svc or fake:
            try:
                if fake:
                    fb_result: dict[str, object] = {
                        "ok": True,
                        "fake": True,
                        "media_id": f"fake-fb-story-{frame.id}",
                    }
                    logger.info("[FAKE] Facebook story | story=%s | frame=%s", story.id, frame.id)
                elif fb_svc is not None:
                    fb_result = fb_svc.post_story(rendered_url)
                else:
                    fb_result = {"ok": True, "skipped": True}

                if fb_result.get("ok") and not fb_result.get("skipped"):
                    frame.facebook_frame_id = (
                        str(fb_result["media_id"]) if fb_result.get("media_id") else None
                    )
                    fb_results.append(fb_result)
                elif not fb_result.get("ok"):
                    logger.warning(
                        "Facebook story frame failed (story=%s frame=%s): %s",
                        story.id,
                        frame.id,
                        fb_result.get("description"),
                    )
            except Exception as exc:
                logger.warning(
                    "Facebook story exception (story=%s frame=%s): %s", story.id, frame.id, exc
                )

    now = datetime.now(UTC).replace(tzinfo=None)
    story.status = "posted"
    story.posted_at = now
    story.updated_at = now
    story.error_message = None
    story.instagram_result_json = json.dumps(ig_results)
    if fb_results:
        story.facebook_result_json = json.dumps(fb_results)
    db.commit()
    db.refresh(story)
    return _story_to_resp(story)
