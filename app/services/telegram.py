import httpx

# Telegram sendMediaGroup caption limit; sendMessage allows up to 4096 chars.
_TG_CAPTION_LIMIT = 1024


class TelegramService:
    def __init__(self, token: str, channel_id: str):
        self._token = token
        self._channel_id = channel_id
        self._base = f"https://api.telegram.org/bot{token}"

    def post_media_group(self, image_urls: list[str], caption: str) -> dict:
        last_message_id: int | None = None
        # Captions > 1024 chars are rejected by sendMediaGroup; send separately.
        inline_caption = caption if len(caption) <= _TG_CAPTION_LIMIT else ""
        with httpx.Client(timeout=30) as client:
            for chunk in _chunks(image_urls, 10):
                media = []
                for i, url in enumerate(chunk):
                    item = {"type": "photo", "media": url}
                    if i == 0 and inline_caption:
                        item["caption"] = inline_caption
                        item["parse_mode"] = "HTML"
                    media.append(item)
                resp = client.post(
                    f"{self._base}/sendMediaGroup",
                    json={"chat_id": self._channel_id, "media": media},
                )
                data = resp.json()
                if not data.get("ok"):
                    return {"ok": False, "description": data.get("description", "Unknown error")}
                result_msgs = data.get("result") or []
                if result_msgs and last_message_id is None:
                    # Capture first message of the first chunk only — that's the
                    # canonical URL anchor for multi-chunk albums.
                    last_message_id = result_msgs[0].get("message_id")
            if not inline_caption and caption:
                resp = client.post(
                    f"{self._base}/sendMessage",
                    json={
                        "chat_id": self._channel_id,
                        "text": caption,
                        "parse_mode": "HTML",
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    return {"ok": False, "description": data.get("description", "Unknown error")}
        return {"ok": True, "message_id": last_message_id}


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
