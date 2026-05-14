def test_create_collection(client):
    resp = client.post("/api/collections", json={"name": "Cycle One"})
    assert resp.status_code == 200
    d = resp.json()
    assert d["name"] == "Cycle One"
    assert d["id"] is not None


def test_list_collections(client):
    client.post("/api/collections", json={"name": "A"})
    client.post("/api/collections", json={"name": "B"})
    data = client.get("/api/collections").json()
    names = [c["name"] for c in data]
    assert "A" in names
    assert "B" in names


def test_update_collection(client):
    cid = client.post("/api/collections", json={"name": "Old"}).json()["id"]
    resp = client.patch(f"/api/collections/{cid}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


def test_delete_collection_soft(client):
    cid = client.post("/api/collections", json={"name": "Del"}).json()["id"]
    client.delete(f"/api/collections/{cid}")
    data = client.get("/api/collections").json()
    assert not any(c["id"] == cid for c in data)


def test_delete_collection_unassigns_series(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    client.delete(f"/api/collections/{cid}")
    detail = client.get(f"/api/series/{sid}").json()
    assert detail["collection"] is None
    assert detail["collection_index"] is None
    assert detail["collection_number"] is None


def test_assign_collection_to_series(client):
    cid = client.post("/api/collections", json={"name": "Saga"}).json()["id"]
    sid = client.post("/api/series", json={"title": "Part 1"}).json()["id"]
    resp = client.put(f"/api/series/{sid}", json={"collection_id": cid})
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["collection"]["id"] == cid
    assert detail["collection"]["name"] == "Saga"


def test_collection_name_appears_in_series_list(client):
    cid = client.post("/api/collections", json={"name": "Epic"}).json()["id"]
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    data = client.get("/api/series").json()
    s = next(item for item in data["items"] if item["id"] == sid)
    assert s["collection_name"] == "Epic"


# ── Collection numbering ──────────────────────────────────────────────────────


def test_auto_index_on_first_assign(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    detail = client.put(f"/api/series/{sid}", json={"collection_id": cid}).json()
    assert detail["collection_index"] == 1
    assert detail["collection_number"] == "1"


def test_auto_index_increments(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    s1 = client.post("/api/series", json={"title": "S1"}).json()["id"]
    s2 = client.post("/api/series", json={"title": "S2"}).json()["id"]
    client.put(f"/api/series/{s1}", json={"collection_id": cid})
    d2 = client.put(f"/api/series/{s2}", json={"collection_id": cid}).json()
    assert d2["collection_index"] == 2
    assert d2["collection_number"] == "2"


def test_collection_number_override(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    detail = client.put(f"/api/series/{sid}", json={"collection_number": "IV"}).json()
    assert detail["collection_number"] == "IV"
    assert detail["collection_index"] == 1  # unchanged


def test_collection_number_empty_string(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    detail = client.put(f"/api/series/{sid}", json={"collection_number": ""}).json()
    assert detail["collection_number"] == ""


def test_unassign_clears_index_and_number(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    client.put(f"/api/series/{sid}", json={"collection_id": cid})
    detail = client.put(f"/api/series/{sid}", json={"collection_id": None}).json()
    assert detail["collection_index"] is None
    assert detail["collection_number"] is None


def test_reassign_to_different_collection_gets_new_index(client):
    c1 = client.post("/api/collections", json={"name": "C1"}).json()["id"]
    c2 = client.post("/api/collections", json={"name": "C2"}).json()["id"]
    sid = client.post("/api/series", json={"title": "S"}).json()["id"]
    client.put(f"/api/series/{sid}", json={"collection_id": c1})
    d2 = client.put(f"/api/series/{sid}", json={"collection_id": c2}).json()
    assert d2["collection_index"] == 1
    assert d2["collection"]["id"] == c2


# ── Collection filter ─────────────────────────────────────────────────────────


def test_filter_series_by_collection(client):
    c1 = client.post("/api/collections", json={"name": "C1"}).json()["id"]
    c2 = client.post("/api/collections", json={"name": "C2"}).json()["id"]
    s1 = client.post("/api/series", json={"title": "In C1"}).json()["id"]
    s2 = client.post("/api/series", json={"title": "In C2"}).json()["id"]
    client.put(f"/api/series/{s1}", json={"collection_id": c1})
    client.put(f"/api/series/{s2}", json={"collection_id": c2})
    data = client.get(f"/api/series?collection_id={c1}").json()
    ids = [s["id"] for s in data["items"]]
    assert s1 in ids
    assert s2 not in ids


# ── Collection counts ─────────────────────────────────────────────────────────


def test_collection_counts_in_list(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    for i in range(3):
        sid = client.post("/api/series", json={"title": f"S{i}"}).json()["id"]
        client.put(f"/api/series/{sid}", json={"collection_id": cid})
    data = client.get("/api/collections").json()
    c = next(x for x in data if x["id"] == cid)
    assert c["series_total"] == 3
    assert c["series_by_status"].get("new", 0) == 3


def test_collection_counts_exclude_deleted(client):
    cid = client.post("/api/collections", json={"name": "C"}).json()["id"]
    s1 = client.post("/api/series", json={"title": "S1"}).json()["id"]
    s2 = client.post("/api/series", json={"title": "S2"}).json()["id"]
    client.put(f"/api/series/{s1}", json={"collection_id": cid})
    client.put(f"/api/series/{s2}", json={"collection_id": cid})
    client.delete(f"/api/series/{s1}")
    data = client.get("/api/collections").json()
    c = next(x for x in data if x["id"] == cid)
    assert c["series_total"] == 1


def test_collection_name_ru_create_and_update(client):
    resp = client.post("/api/collections", json={"name": "Dark Saga", "name_ru": "Тёмная Сага"})
    assert resp.status_code == 200
    d = resp.json()
    assert d["name_ru"] == "Тёмная Сага"

    cid = d["id"]
    resp2 = client.patch(
        f"/api/collections/{cid}", json={"name": "Dark Saga", "name_ru": "Тёмная Сага II"}
    )
    assert resp2.json()["name_ru"] == "Тёмная Сага II"


def test_collection_name_ru_defaults_none(client):
    resp = client.post("/api/collections", json={"name": "Unnamed"})
    assert resp.json()["name_ru"] is None


def test_collection_name_ru_clear(client):
    cid = client.post("/api/collections", json={"name": "X", "name_ru": "Икс"}).json()["id"]
    resp = client.patch(f"/api/collections/{cid}", json={"name": "X", "name_ru": None})
    assert resp.json()["name_ru"] is None
