def test_image_default_status_is_pending(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    img = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    ).json()
    assert img["status"] == "pending"


def test_patch_image_status_skip(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    ).json()["id"]
    resp = client.patch(f"/api/images/{img_id}/status", json={"status": "skip"})
    assert resp.status_code == 200
    detail = resp.json()
    img = next(i for i in detail["images"] if i["id"] == img_id)
    assert img["status"] == "skip"


def test_patch_image_status_pending(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    ).json()["id"]
    client.patch(f"/api/images/{img_id}/status", json={"status": "skip"})
    resp = client.patch(f"/api/images/{img_id}/status", json={"status": "pending"})
    assert resp.status_code == 200
    detail = resp.json()
    img = next(i for i in detail["images"] if i["id"] == img_id)
    assert img["status"] == "pending"


def test_patch_image_status_posted(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    ).json()["id"]
    resp = client.patch(f"/api/images/{img_id}/status", json={"status": "posted"})
    assert resp.status_code == 200
    img = next(i for i in resp.json()["images"] if i["id"] == img_id)
    assert img["status"] == "posted"


def test_patch_image_status_queued_rejected(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    ).json()["id"]
    resp = client.patch(f"/api/images/{img_id}/status", json={"status": "queued"})
    assert resp.status_code == 400


def test_patch_image_status_invalid(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    img_id = client.post(
        f"/api/series/{sid}/images/register",
        json={"r2_key": "images/x.jpg", "original_filename": "x.jpg"},
    ).json()["id"]
    resp = client.patch(f"/api/images/{img_id}/status", json={"status": "nonsense"})
    assert resp.status_code == 400


def test_patch_image_status_not_found(client):
    resp = client.patch("/api/images/no-such-id/status", json={"status": "skip"})
    assert resp.status_code == 404
