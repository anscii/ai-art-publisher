"""Unit tests for the /landing route and landing page content."""


def test_landing_route_returns_200(client):
    r = client.get("/landing")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_landing_has_login_form(client):
    r = client.get("/landing")
    assert 'action="/auth/login"' in r.text
    assert 'name="username"' in r.text


def test_landing_has_aap_classes(client):
    r = client.get("/landing")
    assert "aap-landing" in r.text
    assert "aap-signin-card" in r.text
