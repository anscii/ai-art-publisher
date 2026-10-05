def test_get_settings_empty_by_default(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["anthropic_api_key"] == ""
    assert data["telegram_bot_token"] == ""


def test_update_then_get_masks_token(client):
    client.put("/api/settings", json={"anthropic_api_key": "sk-real-key"})
    resp = client.get("/api/settings")
    assert resp.json()["anthropic_api_key"] == "****"


def test_update_non_secret_field(client):
    client.put(
        "/api/settings",
        json={"default_provider": "openai", "anthropic_default_model": "claude-sonnet-4-6"},
    )
    data = client.get("/api/settings").json()
    assert data["default_provider"] == "openai"
    assert data["anthropic_default_model"] == "claude-sonnet-4-6"


def test_per_provider_model_defaults(client):
    client.put(
        "/api/settings",
        json={
            "anthropic_default_model": "claude-opus-4-7",
            "openai_default_model": "gpt-5.4",
            "google_default_model": "gemini-2.5-flash",
        },
    )
    data = client.get("/api/settings").json()
    assert data["anthropic_default_model"] == "claude-opus-4-7"
    assert data["openai_default_model"] == "gpt-5.4"
    assert data["google_default_model"] == "gemini-2.5-flash"


def test_deepseek_fields_present_in_settings(client):
    data = client.get("/api/settings").json()
    assert "deepseek_api_key" in data
    assert "deepseek_default_model" in data
    assert data["deepseek_api_key"] == ""
    assert data["deepseek_default_model"] == ""


def test_deepseek_api_key_masked(client):
    client.put("/api/settings", json={"deepseek_api_key": "sk-deepseek-key"})
    data = client.get("/api/settings").json()
    assert data["deepseek_api_key"] == "****"


def test_deepseek_default_model_update(client):
    client.put("/api/settings", json={"deepseek_default_model": "deepseek-v4-flash"})
    data = client.get("/api/settings").json()
    assert data["deepseek_default_model"] == "deepseek-v4-flash"


def test_openrouter_fields_present_in_settings(client):
    data = client.get("/api/settings").json()
    assert "openrouter_api_key" in data
    assert "openrouter_default_model" in data
    assert data["openrouter_api_key"] == ""
    assert data["openrouter_default_model"] == ""


def test_openrouter_api_key_masked(client):
    client.put("/api/settings", json={"openrouter_api_key": "sk-or-key"})
    data = client.get("/api/settings").json()
    assert data["openrouter_api_key"] == "****"


def test_openrouter_default_model_update(client):
    client.put("/api/settings", json={"openrouter_default_model": "openrouter/free"})
    data = client.get("/api/settings").json()
    assert data["openrouter_default_model"] == "openrouter/free"


def test_partial_update_preserves_other_fields(client):
    client.put("/api/settings", json={"telegram_channel_id": "@mychannel"})
    client.put("/api/settings", json={"default_provider": "google"})
    data = client.get("/api/settings").json()
    assert data["telegram_channel_id"] == "@mychannel"
    assert data["default_provider"] == "google"


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
    assert client.get("/api/settings/providers").status_code == 403
    assert client.get("/api/stats/ai").status_code == 403
    client.cookies.clear()


def test_settings_allowed_for_admin(client, db, monkeypatch):
    _login_as(client, db, monkeypatch, is_admin=True)
    assert client.get("/api/settings").status_code == 200
    client.cookies.clear()
