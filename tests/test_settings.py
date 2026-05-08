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
    client.put("/api/settings", json={"default_provider": "openai", "default_model": "gpt-4o-mini"})
    data = client.get("/api/settings").json()
    assert data["default_provider"] == "openai"
    assert data["default_model"] == "gpt-4o-mini"


def test_partial_update_preserves_other_fields(client):
    client.put("/api/settings", json={"telegram_channel_id": "@mychannel"})
    client.put("/api/settings", json={"default_provider": "google"})
    data = client.get("/api/settings").json()
    assert data["telegram_channel_id"] == "@mychannel"
    assert data["default_provider"] == "google"
