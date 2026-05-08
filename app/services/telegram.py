import httpx


class TelegramService:
    def __init__(self, token: str, channel_id: str):
        self._token = token
        self._channel_id = channel_id
        self._base = f"https://api.telegram.org/bot{token}"

    def post_media_group(self, image_urls: list[str], caption: str) -> dict:
        results = []
        for chunk in _chunks(image_urls, 10):
            media = []
            for i, url in enumerate(chunk):
                item = {"type": "photo", "media": url}
                if i == 0:
                    item["caption"] = caption
                    item["parse_mode"] = "HTML"
                media.append(item)
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self._base}/sendMediaGroup",
                    json={"chat_id": self._channel_id, "media": media},
                )
            data = resp.json()
            if not data.get("ok"):
                return {"ok": False, "description": data.get("description", "Unknown error")}
            results.append(data)
        return {"ok": True}


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
