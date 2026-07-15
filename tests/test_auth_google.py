from app.config import AppConfig


def test_auth_routes_public_without_credentials(client, monkeypatch, auth_config):
    resp = client.get("/auth/login/google", follow_redirects=False)
    assert resp.status_code != 401

    resp = client.post("/auth/signup", data={"invite_code": "x"}, follow_redirects=False)
    assert resp.status_code != 401

    resp = client.get("/auth/google/callback", follow_redirects=False)
    assert resp.status_code != 401


def test_middleware_enforces_when_only_google_configured(client, monkeypatch):
    """Google-OAuth-only deployment (legacy creds unset) must not leave the
    unscoped routers (images/posts/settings/...) reachable anonymously."""
    monkeypatch.setattr(AppConfig, "google_client_id", "client-id")
    resp = client.get("/api/images", follow_redirects=False)
    assert resp.status_code in (401, 404)  # 401 from middleware, never a 200 payload

    resp = client.get("/api/settings")
    assert resp.status_code == 401
