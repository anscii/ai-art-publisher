import sqlalchemy as sa

from tests.conftest import login_as


def test_get_creates_row_with_defaults(client, db):
    login_as(client, db)
    data = client.get("/api/me/settings").json()
    assert data["default_provider"] == "openrouter"
    assert data["anthropic_api_key"] == ""
    assert data["image_edit_model"] == ""


def test_put_masks_and_encrypts_at_rest(client, db):
    u = login_as(client, db)
    client.put("/api/me/settings", json={"anthropic_api_key": "sk-real"})
    assert client.get("/api/me/settings").json()["anthropic_api_key"] == "****"
    raw = db.execute(
        sa.text("SELECT anthropic_api_key FROM user_settings WHERE user_id = :u"), {"u": u.id}
    ).scalar()
    assert raw and raw != "sk-real"


def test_isolation_between_users(client, db):
    login_as(client, db, email="a@x.com", google_sub="ga")
    client.put("/api/me/settings", json={"anthropic_api_key": "sk-a"})
    login_as(client, db, email="b@x.com", google_sub="gb")
    assert client.get("/api/me/settings").json()["anthropic_api_key"] == ""


def test_partial_put_keeps_other_fields(client, db):
    login_as(client, db)
    client.put("/api/me/settings", json={"default_provider": "google"})
    client.put("/api/me/settings", json={"google_default_model": "gemini-x"})
    data = client.get("/api/me/settings").json()
    assert data["default_provider"] == "google"
    assert data["google_default_model"] == "gemini-x"


def test_test_unknown_provider_404(client, db):
    login_as(client, db)
    assert client.post("/api/me/settings/test/nope").status_code == 404


def test_test_without_key_no_network(client, db):
    login_as(client, db)
    resp = client.post("/api/me/settings/test/anthropic")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_providers_open_to_non_admin(client, db):
    login_as(client, db)
    resp = client.get("/api/settings/providers")
    assert resp.status_code == 200
    assert "anthropic" in resp.json()


def test_put_masked_placeholder_does_not_overwrite_key(client, db):
    u = login_as(client, db)
    client.put("/api/me/settings", json={"anthropic_api_key": "sk-real"})
    client.put("/api/me/settings", json={"anthropic_api_key": "****"})
    from app.models import UserSettings

    db.expire_all()
    assert db.get(UserSettings, u.id).anthropic_api_key == "sk-real"


def test_put_empty_string_clears_key(client, db):
    login_as(client, db)
    client.put("/api/me/settings", json={"anthropic_api_key": "sk-real"})
    client.put("/api/me/settings", json={"anthropic_api_key": ""})
    assert client.get("/api/me/settings").json()["anthropic_api_key"] == ""


def test_default_ai_block_reflects_instance_settings_and_usage(client, db):
    from app.models import AIRequest
    from app.routers.settings import get_or_create_settings

    u = login_as(client, db)
    assert client.get("/api/me/settings").json()["default_ai"] == {
        "enabled": False,
        "used_today": 0,
        "daily_limit": 20,
    }
    s = get_or_create_settings(db)
    s.default_ai_openrouter_key = "sk-inst"
    s.default_ai_daily_limit = 5
    db.add_all(
        [
            AIRequest(
                user_id=u.id,
                kind="draft",
                provider="openrouter",
                model="m",
                via_default_access=True,
            ),
            AIRequest(
                user_id=u.id,
                kind="draft",
                provider="openrouter",
                model="m",
                via_default_access=False,
            ),
        ]
    )
    db.commit()
    assert client.get("/api/me/settings").json()["default_ai"] == {
        "enabled": True,
        "used_today": 1,
        "daily_limit": 5,
    }


def test_put_ignores_default_ai_key(client, db):
    login_as(client, db)
    r = client.put("/api/me/settings", json={"default_ai": {"enabled": True, "daily_limit": 99}})
    assert r.status_code == 200
    assert "default_ai" not in r.json()
    assert client.get("/api/me/settings").json()["default_ai"]["daily_limit"] == 20


def test_style_guide_round_trip_and_reset(client, db):
    login_as(client, db)
    client.put("/api/me/settings", json={"style_guide": "warm cats"})
    assert client.get("/api/me/settings").json()["style_guide"] == "warm cats"
    client.put("/api/me/settings", json={"style_guide": ""})
    assert client.get("/api/me/settings").json()["style_guide"] == ""


def test_style_guide_max_length(client, db):
    login_as(client, db)
    assert client.put("/api/me/settings", json={"style_guide": "x" * 8000}).status_code == 200
    assert client.put("/api/me/settings", json={"style_guide": "x" * 8001}).status_code == 422


def test_default_style_guide_exposed(client, db):
    from app.services.ai.base import DEFAULT_STYLE_GUIDE

    login_as(client, db)
    assert client.get("/api/me/settings").json()["default_style_guide"] == DEFAULT_STYLE_GUIDE
