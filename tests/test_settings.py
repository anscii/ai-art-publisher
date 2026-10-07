def test_get_settings_empty_by_default(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["telegram_bot_token"] == ""


def test_update_then_get_masks_token(client):
    client.put("/api/settings", json={"telegram_bot_token": "123:abc"})
    resp = client.get("/api/settings")
    assert resp.json()["telegram_bot_token"] == "****"
    assert "anthropic_api_key" not in resp.json()


def test_default_ai_openrouter_key_masked(client):
    client.put("/api/settings", json={"default_ai_openrouter_key": "sk-or-key"})
    data = client.get("/api/settings").json()
    assert data["default_ai_openrouter_key"] == "****"
    assert "openrouter_api_key" not in data


def test_default_ai_daily_limit(client):
    assert client.get("/api/settings").json()["default_ai_daily_limit"] == 20
    r = client.put("/api/settings", json={"default_ai_daily_limit": 5})
    assert r.json()["default_ai_daily_limit"] == 5
    client.put("/api/settings", json={"default_ai_daily_limit": 0})
    assert client.get("/api/settings").json()["default_ai_daily_limit"] == 0
    assert client.put("/api/settings", json={"default_ai_daily_limit": -1}).status_code == 422
    assert client.put("/api/settings", json={"default_ai_daily_limit": 1001}).status_code == 422


def test_partial_update_preserves_other_fields(client):
    client.put("/api/settings", json={"telegram_channel_id": "@mychannel"})
    client.put("/api/settings", json={"telegram_bot_token": "123:abc"})
    data = client.get("/api/settings").json()
    assert data["telegram_channel_id"] == "@mychannel"
    assert data["telegram_bot_token"] == "****"


def test_invite_code_readable_plaintext(client):
    client.put("/api/settings", json={"invite_code": "friends-2026"})
    resp = client.get("/api/settings")
    assert resp.json()["invite_code"] == "friends-2026"  # not masked like *_api_key fields


def _login_as(client, db, monkeypatch, *, is_admin):
    from app.config import AppConfig, get_config
    from app.models import User
    from app.routers.auth import COOKIE_NAME, create_user_session_token

    # Enable auth so the no-auth local@localhost admin fallback stays out of the way.
    monkeypatch.setattr(AppConfig, "google_client_id", "client-id")
    u = User(
        email=f"{'admin' if is_admin else 'friend'}@example.com", google_sub="g", is_admin=is_admin
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    client.cookies.set(COOKIE_NAME, create_user_session_token(get_config().session_secret, u.id))


def test_settings_forbidden_for_non_admin(client, db, monkeypatch):
    _login_as(client, db, monkeypatch, is_admin=False)
    assert client.get("/api/settings").status_code == 403
    assert client.put("/api/settings", json={"invite_code": "mine"}).status_code == 403
    assert client.get("/api/settings/providers").status_code == 200  # open since 2A
    assert client.get("/api/stats/ai").status_code == 200
    client.cookies.clear()


def test_settings_allowed_for_admin(client, db, monkeypatch):
    _login_as(client, db, monkeypatch, is_admin=True)
    assert client.get("/api/settings").status_code == 200
    client.cookies.clear()
