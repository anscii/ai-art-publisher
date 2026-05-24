import pytest
import requests

pytestmark = pytest.mark.e2e


def test_filter_row_visible(page, live_server):
    page.goto(live_server)
    page.locator("#filterRow").wait_for(state="visible", timeout=5000)
    assert page.locator("#filterRow").is_visible()


def test_filter_chips_have_all_display_statuses(page, live_server):
    page.goto(live_server)
    page.locator("#filterRow").wait_for(state="visible", timeout=5000)
    groups = {
        el.get_attribute("data-status-group")
        for el in page.locator(".aap-chip[data-status-group]").all()
    }
    assert groups == {"new", "draft", "active", "done", "skip"}


def test_filter_chips_new_and_draft_active_by_default(page, live_server):
    page.goto(live_server)
    page.locator("#filterRow").wait_for(state="visible", timeout=5000)
    active = {
        el.get_attribute("data-status-group")
        for el in page.locator(".aap-chip[data-status-group].is-active").all()
    }
    assert "new" in active
    assert "draft" in active
    assert "active" not in active


def test_search_input_filters_series(page, live_server):
    requests.post(f"{live_server}/api/series", json={"title": "Dragon Forest"})
    requests.post(f"{live_server}/api/series", json={"title": "Moonlit River"})

    page.goto(live_server)
    page.locator("#seriesItems").wait_for()

    page.locator("#seriesSearch").fill("dragon")
    page.wait_for_timeout(500)  # debounce + network

    items = page.locator("#seriesItems .aap-series-row")
    titles = [items.nth(i).text_content() for i in range(items.count())]
    assert any("Dragon Forest" in t for t in titles)
    assert not any("Moonlit River" in t for t in titles)
