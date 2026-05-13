def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_static_files_served(client):
    for path in [
        "/static/style.css",
        "/static/app.js",
        "/static/editor.js",
        "/static/posting.js",
        "/static/settings.js",
    ]:
        assert client.get(path).status_code == 200, f"{path} not served"


def test_lightbox_has_move_to_button(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="lightboxMoveBtn"' in resp.text
    assert 'id="lightboxMoveMenu"' in resp.text
    assert 'data-bs-toggle="dropdown"' in resp.text
    assert 'aria-labelledby="lightboxMoveBtn"' in resp.text
