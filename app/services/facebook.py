import httpx

BASE = "https://graph.facebook.com/v25.0"


class FacebookService:
    def __init__(self, access_token: str, page_id: str):
        self._token = access_token
        self._page_id = page_id

    def post(self, image_urls: list[str], caption: str) -> dict:
        if len(image_urls) == 1:
            return self._post_single(image_urls[0], caption)
        return self._post_album(image_urls[:10], caption)

    def _post_single(self, image_url: str, caption: str) -> dict:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{BASE}/{self._page_id}/photos",
                params={"access_token": self._token},
                json={"url": image_url, "message": caption},
            )
            d = resp.json()
            if "id" not in d:
                return {
                    "ok": False,
                    "description": d.get("error", {}).get("message", "Photo post failed"),
                }
        return {"ok": True, "post_id": d["id"]}

    def _post_album(self, image_urls: list[str], caption: str) -> dict:
        with httpx.Client(timeout=60) as client:
            photo_ids = []
            for url in image_urls:
                resp = client.post(
                    f"{BASE}/{self._page_id}/photos",
                    params={"access_token": self._token},
                    json={"url": url, "published": False},
                )
                d = resp.json()
                if "id" not in d:
                    return {
                        "ok": False,
                        "description": d.get("error", {}).get("message", "Photo upload failed"),
                    }
                photo_ids.append({"media_fbid": d["id"]})

            resp = client.post(
                f"{BASE}/{self._page_id}/feed",
                params={"access_token": self._token},
                json={"message": caption, "attached_media": photo_ids},
            )
            d = resp.json()
            if "id" not in d:
                return {
                    "ok": False,
                    "description": d.get("error", {}).get("message", "Album post failed"),
                }
        return {"ok": True, "post_id": d["id"]}
