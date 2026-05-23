import httpx


class TelegramService:
    def __init__(self, token: str, channel_id: str):
        self._token = token
        self._channel_id = channel_id
        self._base = f"https://api.telegram.org/bot{token}"

    def post_media_group(self, image_urls: list[str], caption: str) -> dict:
        last_message_id: int | None = None
        with httpx.Client(timeout=30) as client:
            for chunk in _chunks(image_urls, 10):
                media = []
                for i, url in enumerate(chunk):
                    item = {"type": "photo", "media": url}
                    if i == 0:
                        item["caption"] = caption
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
                if result_msgs:
                    last_message_id = result_msgs[0].get("message_id")
        return {"ok": True, "message_id": last_message_id}


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
