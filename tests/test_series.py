def test_create_series(client):
    resp = client.post("/api/series", json={"title": "Dragon Forest"})
    assert resp.status_code == 200
    d = resp.json()
    assert d["title"] == "Dragon Forest"
    assert d["status"] == "new"
    assert d["id"] is not None


def test_list_hides_skip_by_default(client):
    client.post("/api/series", json={"title": "Visible"})
    client.post("/api/series", json={"title": "Hidden", "status": "skip"})
    data = client.get("/api/series").json()
    titles = [s["title"] for s in data["items"]]
    assert "Visible" in titles
    assert "Hidden" not in titles


def test_list_filter_by_status(client):
    client.post("/api/series", json={"title": "D1", "status": "draft"})
    client.post("/api/series", json={"title": "N1"})
    data = client.get("/api/series?status=draft").json()
    assert all(s["status"] == "draft" for s in data["items"])
    assert len(data["items"]) == 1


def test_list_filter_multi_status(client):
    client.post("/api/series", json={"title": "D", "status": "draft"})
    client.post("/api/series", json={"title": "A", "status": "approved"})
    client.post("/api/series", json={"title": "N"})
    data = client.get("/api/series?status=draft,approved").json()
    assert data["total"] == 2


def test_pagination(client):
    for i in range(25):
        client.post("/api/series", json={"title": f"S{i}"})
    data = client.get("/api/series?page=1&limit=20").json()
    assert len(data["items"]) == 20
    assert data["total"] == 25


def test_get_detail(client):
    sid = client.post("/api/series", json={"title": "T"}).json()["id"]
    resp = client.get(f"/api/series/{sid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sid


def test_get_detail_404(client):
    assert client.get("/api/series/nonexistent").status_code == 404


def test_update_series(client):
    sid = client.post("/api/series", json={"title": "Old"}).json()["id"]
    resp = client.put(f"/api/series/{sid}", json={"title": "New", "status": "draft"})
    assert resp.json()["title"] == "New"
    assert resp.json()["status"] == "draft"


def test_delete_series(client):
    sid = client.post("/api/series", json={"title": "X"}).json()["id"]
    client.delete(f"/api/series/{sid}")
    # soft delete: hidden from normal view
    assert client.get(f"/api/series/{sid}").status_code == 404
    # but visible in trash
    trash = client.get("/api/trash").json()
    assert any(s["id"] == sid for s in trash["series"])


def test_list_series_search(client):
    client.post("/api/series", json={"title": "Dragon Forest"})
    client.post("/api/series", json={"title": "Moonlit River"})
    client.post("/api/series", json={"title": "Dragon Cave"})
    data = client.get("/api/series?search=dragon").json()
    titles = [s["title"] for s in data["items"]]
    assert "Dragon Forest" in titles
    assert "Dragon Cave" in titles
    assert "Moonlit River" not in titles


def test_get_or_create_unsorted_creates(client):
    resp = client.get("/api/series/unsorted")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Unsorted"
    assert data["id"] is not None


def test_get_or_create_unsorted_idempotent(client):
    first = client.get("/api/series/unsorted").json()["id"]
    second = client.get("/api/series/unsorted").json()["id"]
    assert first == second
    # only one series named Unsorted should exist
    listed = client.get("/api/series").json()
    unsorted_entries = [s for s in listed["items"] if s["title"] == "Unsorted"]
    assert len(unsorted_entries) == 1


def _register_image(client, series_id, key="images/test.jpg"):
    return client.post(
        f"/api/series/{series_id}/images/register",
        json={"r2_key": key, "original_filename": "test.jpg"},
    ).json()["id"]


def test_save_queue_sets_queued_and_resets_pending(client):
    sid = client.post("/api/series", json={"title": "Q"}).json()["id"]
    img_a = _register_image(client, sid, "a.jpg")
    img_b = _register_image(client, sid, "b.jpg")
    img_c = _register_image(client, sid, "c.jpg")
    # mark img_c as posted — should be untouched
    client.patch(f"/api/images/{img_c}/status", json={"status": "posted"})

    resp = client.put(f"/api/series/{sid}/queue", json={"image_ids": [img_a]})
    assert resp.status_code == 200
    images = {i["id"]: i for i in resp.json()["images"]}
    assert images[img_a]["status"] == "queued"
    assert images[img_b]["status"] == "pending"
    assert images[img_c]["status"] == "posted"


def test_save_queue_clears_previous_queue(client):
    sid = client.post("/api/series", json={"title": "Q2"}).json()["id"]
    img_a = _register_image(client, sid, "qa.jpg")
    img_b = _register_image(client, sid, "qb.jpg")
    # queue both
    client.put(f"/api/series/{sid}/queue", json={"image_ids": [img_a, img_b]})
    # now save with only img_b — img_a should revert to pending
    resp = client.put(f"/api/series/{sid}/queue", json={"image_ids": [img_b]})
    images = {i["id"]: i for i in resp.json()["images"]}
    assert images[img_a]["status"] == "pending"
    assert images[img_b]["status"] == "queued"
