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
    assert client.get(f"/api/series/{sid}").status_code == 404
