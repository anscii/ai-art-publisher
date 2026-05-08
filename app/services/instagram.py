import httpx

BASE = "https://graph.instagram.com/v21.0"


class InstagramService:
    def __init__(self, access_token: str, user_id: str):
        self._token = access_token
        self._user_id = user_id

    def post(self, image_urls: list[str], caption: str) -> dict:
        if len(image_urls) == 1:
            return self._post_single(image_urls[0], caption)
        return self._post_carousel(image_urls[:10], caption)

    def _post_single(self, image_url: str, caption: str) -> dict:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{BASE}/{self._user_id}/media",
                params={"access_token": self._token},
                json={"image_url": image_url, "caption": caption},
            )
            data = resp.json()
            if "id" not in data:
                return {
                    "ok": False,
                    "description": data.get("error", {}).get("message", "Create failed"),
                }
            resp2 = client.post(
                f"{BASE}/{self._user_id}/media_publish",
                params={"access_token": self._token},
                json={"creation_id": data["id"]},
            )
            data2 = resp2.json()
            if "id" not in data2:
                return {
                    "ok": False,
                    "description": data2.get("error", {}).get("message", "Publish failed"),
                }
        return {"ok": True, "media_id": data2["id"]}

    def _post_carousel(self, image_urls: list[str], caption: str) -> dict:
        with httpx.Client(timeout=60) as client:
            child_ids = []
            for url in image_urls:
                resp = client.post(
                    f"{BASE}/{self._user_id}/media",
                    params={"access_token": self._token},
                    json={"image_url": url, "is_carousel_item": True},
                )
                d = resp.json()
                if "id" not in d:
                    return {
                        "ok": False,
                        "description": d.get("error", {}).get("message", "Item create failed"),
                    }
                child_ids.append(d["id"])

            resp = client.post(
                f"{BASE}/{self._user_id}/media",
                params={"access_token": self._token},
                json={"media_type": "CAROUSEL", "children": child_ids, "caption": caption},
            )
            d = resp.json()
            if "id" not in d:
                return {
                    "ok": False,
                    "description": d.get("error", {}).get("message", "Carousel create failed"),
                }

            resp2 = client.post(
                f"{BASE}/{self._user_id}/media_publish",
                params={"access_token": self._token},
                json={"creation_id": d["id"]},
            )
            d2 = resp2.json()
            if "id" not in d2:
                return {
                    "ok": False,
                    "description": d2.get("error", {}).get("message", "Publish failed"),
                }
        return {"ok": True, "media_id": d2["id"]}
