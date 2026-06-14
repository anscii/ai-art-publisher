import asyncio
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


async def _post_one_frame(
    client,
    channel,
    image_bytes: bytes,
    link_url: str | None = None,
    link_area: dict | None = None,
) -> dict:
    from telethon.tl.functions.stories import SendStoryRequest
    from telethon.tl.types import InputMediaUploadedPhoto, InputPrivacyValueAllowAll

    uploaded = await client.upload_file(BytesIO(image_bytes), file_name="story.jpg")
    kwargs: dict = dict(
        peer=channel,
        media=InputMediaUploadedPhoto(file=uploaded),
        privacy_rules=[InputPrivacyValueAllowAll()],
        period=86400,
    )
    if link_url:
        from telethon.tl.types import MediaAreaCoordinates, MediaAreaUrl

        a = link_area or {}
        coords = MediaAreaCoordinates(
            x=float(a.get("x", 75.0)),
            y=float(a.get("y", 82.0)),
            w=float(a.get("w", 50.0)),
            h=float(a.get("h", 10.0)),
            rotation=0.0,
        )
        kwargs["media_areas"] = [MediaAreaUrl(coordinates=coords, url=link_url)]
    result = await client(SendStoryRequest(**kwargs))
    story_id: int | None = None
    returned_areas = None
    for update in getattr(result, "updates", []):
        story = getattr(update, "story", None)
        if story is not None:
            story_id = getattr(story, "id", None)
            returned_areas_list = getattr(story, "media_areas", None)
            if returned_areas_list:
                returned_areas = [a.to_dict() for a in returned_areas_list]
            break
    logger.info(
        "tg story frame posted: story_id=%s link_url=%r returned_media_areas=%r",
        story_id,
        link_url,
        returned_areas,
    )
    return {"ok": True, "story_id": story_id}


async def _post_stories_async(
    api_id: int,
    api_hash: str,
    session_string: str,
    channel_id: str,
    images: list[bytes],
    link_urls: list[str | None] | None = None,
    link_areas: list[dict | None] | None = None,
) -> list[dict]:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    results: list[dict] = []
    _link_urls = link_urls or [None] * len(images)
    _link_areas = link_areas or [None] * len(images)
    logger.info(f"tg stories debug: {_link_urls=} {_link_areas=}")
    try:
        await client.connect()
        channel = await client.get_entity(channel_id)
        for image_bytes, link_url, link_area in zip(images, _link_urls, _link_areas):
            try:
                results.append(
                    await _post_one_frame(client, channel, image_bytes, link_url, link_area)
                )
            except Exception as exc:
                logger.error("Telegram story frame failed: %s", exc)
                results.append({"ok": False, "description": str(exc)})
    except Exception as exc:
        logger.error("Telegram story post failed: %s", exc)
        while len(results) < len(images):
            results.append({"ok": False, "description": str(exc)})
    finally:
        await client.disconnect()
    return results


def post_stories(
    api_id: int,
    api_hash: str,
    session_string: str,
    channel_id: str,
    images: list[bytes],
    link_urls: list[str | None] | None = None,
    link_areas: list[dict | None] | None = None,
) -> list[dict]:
    return asyncio.run(
        _post_stories_async(
            api_id, api_hash, session_string, channel_id, images, link_urls, link_areas
        )
    )
