"""E2E: Descriptions section is always visible in the editor."""

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
    page.locator(f"#descBody-{series_id}").wait_for(state="visible", timeout=5000)


def test_descriptions_section_always_visible(page, live_server):
    """Descriptions section is visible immediately — no collapse in new design."""
    series_id = _create_series(page, live_server)
    _open_series(page, live_server, series_id)
    assert page.locator(f"#descBody-{series_id}").is_visible()


def test_descriptions_fields_present(page, live_server):
    """All key description fields exist in the editor."""
    series_id = _create_series(page, live_server)
    _open_series(page, live_server, series_id)
    assert page.locator("#f_pub_title").is_visible()
    assert page.locator("#f_desc_en").is_visible()
    assert page.locator("#f_desc_ru").is_visible()
    assert page.locator("#f_tags_ig").is_visible()


def test_descriptions_show_series_content(page, live_server):
    """Series with a title shows it in the publication title field."""
    series_id = _create_series(page, live_server)
    r = page.request.put(
        f"{live_server}/api/series/{series_id}",
        data=json.dumps({"title": "Cosmic Horror Gallery"}),
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    _open_series(page, live_server, series_id)
    assert page.locator("#f_pub_title").input_value() == "Cosmic Horror Gallery"
