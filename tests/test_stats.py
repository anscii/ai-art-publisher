from app.models import AIVariant, Series


def _make_series(db, name="s1"):
    s = Series(name=name)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_variant(db, series_id, provider="anthropic", model="claude-sonnet-4-6", cost=0.01):
    v = AIVariant(series_id=series_id, provider=provider, model=model, cost_usd=cost)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def test_ai_stats_empty(client):
    resp = client.get("/api/stats/ai")
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == []
    assert data["total_generated"] == 0
    assert data["total_chosen"] == 0
    assert data["total_cost_usd"] == 0.0


def test_ai_stats_counts_and_cost(client, db):
    s = _make_series(db)
    _make_variant(db, s.id, provider="anthropic", model="claude-sonnet-4-6", cost=0.01)
    _make_variant(db, s.id, provider="anthropic", model="claude-sonnet-4-6", cost=0.02)
    _make_variant(db, s.id, provider="google", model="gemini-2.5-flash", cost=0.005)

    resp = client.get("/api/stats/ai")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_generated"] == 3
    assert data["total_chosen"] == 0
    assert abs(data["total_cost_usd"] - 0.035) < 1e-9

    rows = {r["model"]: r for r in data["rows"]}
    assert rows["claude-sonnet-4-6"]["generated"] == 2
    assert abs(rows["claude-sonnet-4-6"]["total_cost_usd"] - 0.03) < 1e-9
    assert rows["gemini-2.5-flash"]["generated"] == 1


def test_ai_stats_chosen_and_selection_rate(client, db):
    s = _make_series(db)
    v1 = _make_variant(db, s.id, provider="anthropic", model="claude-sonnet-4-6", cost=0.01)
    _make_variant(db, s.id, provider="anthropic", model="claude-sonnet-4-6", cost=0.01)

    s.chosen_variant_id = v1.id
    db.commit()

    resp = client.get("/api/stats/ai")
    assert resp.status_code == 200
    data = resp.json()
    row = data["rows"][0]
    assert row["generated"] == 2
    assert row["chosen"] == 1
    assert row["selection_rate"] == 50.0


def test_ai_stats_cost_per_selection(client, db):
    s = _make_series(db)
    v = _make_variant(db, s.id, provider="openai", model="gpt-5.4-mini", cost=0.008)
    _make_variant(db, s.id, provider="openai", model="gpt-5.4-mini", cost=0.008)

    # no chosen yet → cost_per_selection is None
    resp = client.get("/api/stats/ai")
    row = resp.json()["rows"][0]
    assert row["cost_per_selection"] is None

    # mark one as chosen
    s.chosen_variant_id = v.id
    db.commit()

    resp = client.get("/api/stats/ai")
    row = resp.json()["rows"][0]
    assert row["cost_per_selection"] is not None
    assert abs(row["cost_per_selection"] - 0.016) < 1e-9
