import httpx

BASE = "https://api.pinterest.com/v5"


class PinterestService:
    def __init__(self, access_token: str):
        self._token = access_token

    def post_pins(self, board_id: str, image_urls: list[str], title: str, description: str) -> dict:
        pin_ids = []
        with httpx.Client(timeout=60) as client:
            for url in image_urls:
                r = self._post_pin(client, board_id, url, title, description)
                if not r.get("ok"):
                    return r
                pin_ids.append(r["pin_id"])
        return {"ok": True, "pin_ids": pin_ids}

    def create_board(self, name: str) -> dict:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                f"{BASE}/boards",
                headers={"Authorization": f"Bearer {self._token}"},
                json={"name": name, "privacy": "SECRET"},
            )
            d = resp.json()
            if "id" not in d:
                return {"ok": False, "description": d.get("message", "Board creation failed")}
            return {"ok": True, "board_id": d["id"]}

    def _post_pin(
        self, client: httpx.Client, board_id: str, image_url: str, title: str, description: str
    ) -> dict:
        resp = client.post(
            f"{BASE}/pins",
            headers={"Authorization": f"Bearer {self._token}"},
            json={
                "board_id": board_id,
                "media_source": {"source_type": "image_url", "url": image_url},
                "title": title,
                "description": description,
                "alt_text": title,
            },
        )
        d = resp.json()
        if "id" not in d:
            return {"ok": False, "description": d.get("message", "Pin creation failed")}
        return {"ok": True, "pin_id": d["id"]}
