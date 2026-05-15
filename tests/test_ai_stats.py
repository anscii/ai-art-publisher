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
    assert data["generated"] == []
    assert data["chosen"] == []


def test_stats_generated(client, db):
    s = _series(db)
    _variant(db, s.id)
    _variant(db, s.id)
    _variant(db, s.id, provider="openai", model="gpt-4o")
    db.commit()

    data = client.get("/api/stats/ai").json()
    assert len(data["generated"]) == 2
    assert data["generated"][0] == {"provider": "anthropic", "model": "claude-opus", "count": 2}
    assert data["generated"][1] == {"provider": "openai", "model": "gpt-4o", "count": 1}
    assert data["chosen"] == []


def test_stats_chosen_via_put(client, db):
    s = _series(db)
    v = _variant(db, s.id)
    db.commit()

    r = client.put(f"/api/series/{s.id}", json={"chosen_variant_id": v.id})
    assert r.status_code == 200

    data = client.get("/api/stats/ai").json()
    assert data["chosen"] == [{"provider": "anthropic", "model": "claude-opus", "count": 1}]


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
    assert data["chosen"] == []
