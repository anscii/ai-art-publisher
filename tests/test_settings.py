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


def test_partial_update_preserves_other_fields(client):
    client.put("/api/settings", json={"telegram_channel_id": "@mychannel"})
    client.put("/api/settings", json={"default_provider": "google"})
    data = client.get("/api/settings").json()
    assert data["telegram_channel_id"] == "@mychannel"
    assert data["default_provider"] == "google"
