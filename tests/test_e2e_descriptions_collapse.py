"""E2E: Descriptions card collapses when all text fields are empty."""

import json

import pytest

pytestmark = pytest.mark.e2e


def _create_series(page, live_server):
    r = page.request.post(
        f"{live_server}/api/series",
        data=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    return r.json()["id"]


def _open_series(page, live_server, series_id):
    page.goto(live_server)
    page.wait_for_function("() => typeof selectSeries === 'function'", timeout=10000)
    page.evaluate(f"selectSeries('{series_id}')")
    page.locator(f"#descBody-{series_id}").wait_for(state="attached", timeout=5000)


def test_descriptions_card_collapsed_for_new_series(page, live_server):
    """Empty series: body hidden, card header still visible."""
    series_id = _create_series(page, live_server)
    _open_series(page, live_server, series_id)
    body = page.locator(f"#descBody-{series_id}")
    assert not body.is_visible(), "Descriptions body should be hidden when all fields empty"


def test_descriptions_card_expands_on_toggle(page, live_server):
    """Clicking the chevron button expands the collapsed card."""
    series_id = _create_series(page, live_server)
    _open_series(page, live_server, series_id)
    page.locator('button[title="Toggle descriptions"]').click()
    body = page.locator(f"#descBody-{series_id}")
    body.wait_for(state="visible", timeout=3000)
    assert body.is_visible()


def test_descriptions_card_expanded_when_has_content(page, live_server):
    """Series with a title renders the card expanded by default."""
    series_id = _create_series(page, live_server)
    r = page.request.put(
        f"{live_server}/api/series/{series_id}",
        data=json.dumps({"title": "A title"}),
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    _open_series(page, live_server, series_id)
    body = page.locator(f"#descBody-{series_id}")
    assert body.is_visible(), "Descriptions body should be visible when series has content"
