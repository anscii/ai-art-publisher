import asyncio
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


async def _post_one_frame(client, channel, image_bytes: bytes) -> dict:
    from telethon.tl.functions.stories import SendStoryRequest
    from telethon.tl.types import InputMediaUploadedPhoto, InputPrivacyValueAllowAll

    uploaded = await client.upload_file(BytesIO(image_bytes), file_name="story.jpg")
    result = await client(
        SendStoryRequest(
            peer=channel,
            media=InputMediaUploadedPhoto(file=uploaded),
            privacy_rules=[InputPrivacyValueAllowAll()],
            period=86400,
        )
    )
    story_id: int | None = None
    for update in getattr(result, "updates", []):
        story = getattr(update, "story", None)
        if story is not None:
            story_id = getattr(story, "id", None)
            break
    return {"ok": True, "story_id": story_id}


async def _post_stories_async(
    api_id: int,
    api_hash: str,
    session_string: str,
    channel_id: str,
    images: list[bytes],
) -> list[dict]:
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    results: list[dict] = []
    try:
        await client.connect()
        channel = await client.get_entity(channel_id)
        for image_bytes in images:
            try:
                results.append(await _post_one_frame(client, channel, image_bytes))
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
) -> list[dict]:
    return asyncio.run(_post_stories_async(api_id, api_hash, session_string, channel_id, images))
