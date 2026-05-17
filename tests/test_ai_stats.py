from app.models import AIVariant, Series


def _series(db, name="s"):
    s = Series(name=name, title=name)
    db.add(s)
    db.flush()
    return s


def _variant(db, series_id, provider="anthropic", model="claude-opus"):
    v = AIVariant(
        series_id=series_id,
        provider=provider,
        model=model,
        title="T",
        title_ru="",
        description_en="d",
        description_ru="r",
        tags_instagram="[]",
        tags_telegram="[]",
    )
    db.add(v)
    db.flush()
    return v


def test_stats_empty(client):
    r = client.get("/api/stats/ai")
    assert r.status_code == 200
    data = r.json()
    assert data["rows"] == []
    assert data["total_generated"] == 0
    assert data["total_chosen"] == 0


def test_stats_generated(client, db):
    s = _series(db)
    _variant(db, s.id)
    _variant(db, s.id)
    _variant(db, s.id, provider="openai", model="gpt-4o")
    db.commit()

    data = client.get("/api/stats/ai").json()
    assert data["total_generated"] == 3
    assert data["total_chosen"] == 0
    rows = {r["model"]: r for r in data["rows"]}
    assert rows["claude-opus"]["generated"] == 2
    assert rows["claude-opus"]["chosen"] == 0
    assert rows["gpt-4o"]["generated"] == 1


def test_stats_chosen_via_put(client, db):
    s = _series(db)
    v = _variant(db, s.id)
    db.commit()

    r = client.put(f"/api/series/{s.id}", json={"chosen_variant_id": v.id})
    assert r.status_code == 200

    data = client.get("/api/stats/ai").json()
    assert data["total_chosen"] == 1
    row = data["rows"][0]
    assert row["provider"] == "anthropic"
    assert row["model"] == "claude-opus"
    assert row["chosen"] == 1


def test_stats_chosen_not_sent_when_null(client, db):
    s = _series(db)
    v = _variant(db, s.id)
    db.commit()

    client.put(f"/api/series/{s.id}", json={"chosen_variant_id": v.id})
    # Save again without chosen_variant_id — DB value must stay
    client.put(f"/api/series/{s.id}", json={"title": "updated"})

    db.refresh(s)
    assert s.chosen_variant_id == v.id


def test_chosen_nulled_on_variant_delete(client, db):
    s = _series(db)
    v = _variant(db, s.id)
    db.commit()

    client.put(f"/api/series/{s.id}", json={"chosen_variant_id": v.id})
    client.delete(f"/api/ai_variants/{v.id}")

    db.refresh(s)
    assert s.chosen_variant_id is None

    data = client.get("/api/stats/ai").json()
    assert data["rows"] == []
    assert data["total_chosen"] == 0
