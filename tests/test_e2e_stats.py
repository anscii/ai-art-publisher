import pytest

pytestmark = pytest.mark.e2e

_STATS_BTN = "#navStats"
_STATS_PANEL = "#statsPanel"


def test_stats_panel_opens(page, live_server):
    page.goto(live_server)
    page.locator(_STATS_BTN).click()
    page.locator(_STATS_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(_STATS_PANEL).is_visible()
    page.locator("#statsContent").wait_for(state="visible", timeout=5000)
    assert page.locator("#statsContent").inner_text().strip() != ""


def test_stats_panel_shows_aap_page_chrome(page, live_server):
    """Stats panel renders the AAP page chrome: icon tile + title + kicker."""
    page.goto(live_server)
    page.locator(_STATS_BTN).click()
    page.locator(_STATS_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(f"{_STATS_PANEL} .aap-page__title").is_visible()
    assert page.locator(f"{_STATS_PANEL} .aap-page__icon").is_visible()


def test_stats_panel_survives_reload(page, live_server):
    """Reloading ?view=stats stays on stats panel, not redirected to list/editor."""
    page.goto(f"{live_server}/?view=stats")
    page.locator(_STATS_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(_STATS_PANEL).is_visible()
    assert not page.locator("#seriesListPanel").is_visible()


def test_stats_range_buttons_present(page, live_server):
    """Stats panel header contains This week and All time range buttons."""
    page.goto(live_server)
    page.locator(_STATS_BTN).click()
    page.locator(_STATS_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator("#statsRangeAll").is_visible()
    assert page.locator("#statsRangeWeek").is_visible()


def test_stats_empty_or_aap_table(page, live_server):
    """Stats panel renders either an .aap-table or an empty-state paragraph."""
    page.goto(live_server)
    page.locator(_STATS_BTN).click()
    page.locator(_STATS_PANEL).wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(800)
    has_table = page.locator(f"{_STATS_PANEL} .aap-table").count() > 0
    has_empty = page.locator(f"{_STATS_PANEL} #statsContent p").count() > 0
    assert has_table or has_empty


def test_stats_panel_shows_data_after_generation(page, live_server):
    r = page.request.post(
        f"{live_server}/api/series",
        data="{}",
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    series_id = r.json()["id"]

    r = page.request.post(
        f"{live_server}/api/series/{series_id}/generate",
        data='{"hint": "stats test"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()

    page.goto(live_server)
    page.locator(_STATS_BTN).click()
    page.locator(_STATS_PANEL).wait_for(state="visible", timeout=5000)
    page.locator(f"{_STATS_PANEL} .aap-table").wait_for(state="visible", timeout=5000)
    assert page.locator(f"{_STATS_PANEL} .aap-table").is_visible()
    assert page.locator(f"{_STATS_PANEL} .aap-table__row").count() >= 1


def test_stats_table_sortable(page, live_server):
    r = page.request.post(
        f"{live_server}/api/series",
        data="{}",
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    series_id = r.json()["id"]
    page.request.post(
        f"{live_server}/api/series/{series_id}/generate",
        data='{"hint": "sort test"}',
        headers={"Content-Type": "application/json"},
    )

    page.goto(live_server)
    page.locator(_STATS_BTN).click()
    page.locator(f"{_STATS_PANEL} .aap-table").wait_for(state="visible", timeout=5000)

    # click "Provider" header span — sort indicator appears
    page.locator(f"{_STATS_PANEL} .aap-table__head span").first.click()
    header_text = page.locator(f"{_STATS_PANEL} .aap-table__head span").first.inner_text()
    assert "▾" in header_text or "▴" in header_text

    # click again — direction flips
    page.locator(f"{_STATS_PANEL} .aap-table__head span").first.click()
    header_text2 = page.locator(f"{_STATS_PANEL} .aap-table__head span").first.inner_text()
    assert header_text2 != header_text


def test_stats_kicker_updates_after_load(page, live_server):
    """Stats kicker is non-empty after data loads."""
    page.goto(live_server)
    page.locator(_STATS_BTN).click()
    page.locator(_STATS_PANEL).wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(800)
    kicker = page.locator("#statsKicker")
    assert kicker.is_visible()
    assert kicker.inner_text().strip() != ""
