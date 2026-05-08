import io
from unittest.mock import MagicMock, patch


def _make_series(client, title="S"):
    return client.post("/api/series", json={"title": title}).json()["id"]


def _upload(client, series_id, filename="1680030203290_out.jpg"):
    files = {"files": (filename, io.BytesIO(b"fake"), "image/jpeg")}
    with patch("app.routers.images.get_storage_from_settings") as mock:
        storage = MagicMock()
        storage.upload_bytes.return_value = "images/test.jpg"
        mock.return_value = storage
        return client.post(f"/api/series/{series_id}/images", files=files)


def test_upload_parses_timestamp(client):
    sid = _make_series(client)
    resp = _upload(client, sid, filename="1680030203290_out.jpg")
    assert resp.status_code == 200
    img = resp.json()[0]
    assert img["original_filename"] == "1680030203290_out.jpg"
    assert img["original_created_at"] is not None


def test_upload_unknown_filename(client):
    sid = _make_series(client)
    resp = _upload(client, sid, filename="my_art.jpg")
    assert resp.status_code == 200
    assert resp.json()[0]["original_created_at"] is None


def test_register_image(client):
    sid = _make_series(client)
    resp = client.post(
        f"/api/series/{sid}/images/register",
        json={
            "r2_key": "images/bulk.jpg",
            "original_filename": "1680030203290_out.jpg",
            "original_created_at": "2023-03-28T19:03:23Z",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["r2_key"] == "images/bulk.jpg"


def test_reorder_images(client):
    sid = _make_series(client)
    ids = []
    for i in range(3):
        resp = client.post(
            f"/api/series/{sid}/images/register",
            json={
                "r2_key": f"images/{i}.jpg",
                "original_filename": f"{i}.jpg",
            },
        )
        ids.append(resp.json()["id"])
    client.put(f"/api/series/{sid}/images/reorder", json={"image_ids": list(reversed(ids))})
    detail = client.get(f"/api/series/{sid}").json()
    result_ids = [img["id"] for img in detail["images"]]
    assert result_ids == list(reversed(ids))


def test_move_image(client):
    src = _make_series(client, "Source")
    dst = _make_series(client, "Dest")
    img_id = client.post(
        f"/api/series/{src}/images/register",
        json={
            "r2_key": "images/x.jpg",
            "original_filename": "x.jpg",
        },
    ).json()["id"]
    client.put(f"/api/images/{img_id}/move", json={"target_series_id": dst})
    assert client.get(f"/api/series/{src}").json()["images"] == []
    assert len(client.get(f"/api/series/{dst}").json()["images"]) == 1


def test_delete_image(client):
    sid = _make_series(client)
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={
            "r2_key": "images/y.jpg",
            "original_filename": "y.jpg",
        },
    ).json()["id"]
    with patch("app.routers.images.get_storage_from_settings") as mock:
        mock.return_value = MagicMock()
        client.delete(f"/api/images/{img_id}")
    assert client.get(f"/api/series/{sid}").json()["images"] == []
