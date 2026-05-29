import logging
import time

import httpx

logger = logging.getLogger(__name__)

BASE = "https://graph.instagram.com/v25.0"
_POLL_INTERVAL = 3  # seconds between status checks
_POLL_TIMEOUT = 120  # max seconds to wait for FINISHED


class InstagramService:
    def __init__(self, access_token: str, user_id: str):
        self._token = access_token
        self._user_id = user_id

    def post(self, image_urls: list[str], caption: str) -> dict:
        if len(image_urls) == 1:
            return self._post_single(image_urls[0], caption)
        return self._post_carousel(image_urls[:10], caption)

    def _wait_for_container(self, client: httpx.Client, container_id: str) -> str | None:
        """Poll container status until FINISHED or ERROR/timeout. Returns error message or None."""
        deadline = time.monotonic() + _POLL_TIMEOUT
        while time.monotonic() < deadline:
            r = client.get(
                f"{BASE}/{container_id}",
                params={"fields": "status_code", "access_token": self._token},
            )
            status = r.json().get("status_code", "")
            if status == "FINISHED":
                return None
            if status == "ERROR":
                return "Instagram container processing failed (ERROR)"
            time.sleep(_POLL_INTERVAL)
        return f"Instagram container not ready after {_POLL_TIMEOUT}s"

    def _fetch_permalink(self, client: httpx.Client, media_id: str) -> str | None:
        """Fetch the permalink URL for a published media item. Returns None on failure."""
        try:
            r = client.get(
                f"{BASE}/{media_id}",
                params={"fields": "permalink", "access_token": self._token},
                timeout=10,
            )
            return r.json().get("permalink")
        except Exception as exc:
            logger.warning("Failed to fetch Instagram permalink for %s: %s", media_id, exc)
            return None

    def _create_and_publish(
        self,
        client: httpx.Client,
        create_json: dict,
        *,
        create_err: str = "Create failed",
        publish_err: str = "Publish failed",
    ) -> dict:
        """Create a single media container, wait for it, then publish. Returns ok + media_id."""
        resp = client.post(
            f"{BASE}/{self._user_id}/media",
            params={"access_token": self._token},
            json=create_json,
        )
        data = resp.json()
        if "id" not in data:
            return {"ok": False, "description": data.get("error", {}).get("message", create_err)}
        err = self._wait_for_container(client, data["id"])
        if err:
            return {"ok": False, "description": err}
        resp2 = client.post(
            f"{BASE}/{self._user_id}/media_publish",
            params={"access_token": self._token},
            json={"creation_id": data["id"]},
        )
        data2 = resp2.json()
        if "id" not in data2:
            return {"ok": False, "description": data2.get("error", {}).get("message", publish_err)}
        return {"ok": True, "media_id": data2["id"]}

    def _post_single(self, image_url: str, caption: str) -> dict:
        with httpx.Client(timeout=60) as client:
            result = self._create_and_publish(client, {"image_url": image_url, "caption": caption})
            if not result.get("ok"):
                return result
            result["permalink"] = self._fetch_permalink(client, str(result["media_id"]))
            return result

    def post_story(self, image_url: str) -> dict:
        with httpx.Client(timeout=60) as client:
            return self._create_and_publish(
                client,
                {"image_url": image_url, "media_type": "STORIES"},
                create_err="Story container create failed",
                publish_err="Story publish failed",
            )

    def _post_carousel(self, image_urls: list[str], caption: str) -> dict:
        permalink: str | None = None
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
                err = self._wait_for_container(client, d["id"])
                if err:
                    return {"ok": False, "description": err}
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
            err = self._wait_for_container(client, d["id"])
            if err:
                return {"ok": False, "description": err}

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
            permalink = self._fetch_permalink(client, d2["id"])
        return {"ok": True, "media_id": d2["id"], "permalink": permalink}
