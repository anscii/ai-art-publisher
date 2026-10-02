from app.models import User


def _login_as(client, db, email="me@example.com", google_sub="g-me"):
    from app.config import get_config
    from app.routers.auth import COOKIE_NAME, create_user_session_token

    u = User(email=email, google_sub=google_sub)
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_user_session_token(get_config().session_secret, u.id)
    client.cookies.set(COOKIE_NAME, token)
    return u


def test_list_series_only_shows_own(client, db):
    _login_as(client, db, "a@example.com", "g-a")
    client.post("/api/series", json={"title": "A's series"})
    client.cookies.clear()

    _login_as(client, db, "b@example.com", "g-b")
    client.post("/api/series", json={"title": "B's series"})

    resp = client.get("/api/series")
    titles = [s["title"] for s in resp.json()["items"]]
    assert titles == ["B's series"]


def test_get_other_users_series_404s(client, db):
    _login_as(client, db, "a@example.com", "g-a")
    sid = client.post("/api/series", json={"title": "A's series"}).json()["id"]
    client.cookies.clear()

    _login_as(client, db, "b@example.com", "g-b")
    resp = client.get(f"/api/series/{sid}")
    assert resp.status_code == 404


def test_delete_other_users_series_404s(client, db):
    _login_as(client, db, "a@example.com", "g-a")
    sid = client.post("/api/series", json={"title": "A's series"}).json()["id"]
    client.cookies.clear()

    _login_as(client, db, "b@example.com", "g-b")
    resp = client.delete(f"/api/series/{sid}")
    assert resp.status_code == 404


def test_create_series_sets_owner(client, db):
    user = _login_as(client, db)
    sid = client.post("/api/series", json={"title": "Mine"}).json()["id"]
    from app.models import Series

    series = db.get(Series, sid)
    assert series.user_id == user.id
