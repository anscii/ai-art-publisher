import pytest
import requests

pytestmark = pytest.mark.e2e


def test_filter_dropdown_opens(page, live_server):
    page.goto(live_server)
    page.locator("#filterBtn").click()
    page.locator("#statusFilterMenu").wait_for(state="visible", timeout=5000)
    assert page.locator("#statusFilterMenu").is_visible()


def test_filter_dropdown_has_all_statuses(page, live_server):
    page.goto(live_server)
    page.locator("#filterBtn").click()
    page.locator("#statusFilterMenu").wait_for(state="visible", timeout=5000)
    expected = {"new", "draft", "approved", "scheduled", "partial_posted", "posted", "skip"}
    values = {
        el.get_attribute("value")
        for el in page.locator("#statusFilterMenu input[type=checkbox]").all()
    }
    assert values == expected


def test_search_input_filters_series(page, live_server):
    requests.post(f"{live_server}/api/series", json={"title": "Dragon Forest"})
    requests.post(f"{live_server}/api/series", json={"title": "Moonlit River"})

    page.goto(live_server)
    page.locator("#seriesItems").wait_for()

    page.locator("#seriesSearch").fill("dragon")
    page.wait_for_timeout(500)  # debounce + network

    items = page.locator("#seriesItems .series-item")
    titles = [items.nth(i).text_content() for i in range(items.count())]
    assert any("Dragon Forest" in t for t in titles)
    assert not any("Moonlit River" in t for t in titles)
