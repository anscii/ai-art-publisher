import pytest

pytestmark = pytest.mark.e2e


def test_stats_panel_opens(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="Stats").click()
    page.locator("#statsPanel").wait_for(state="visible", timeout=5000)
    assert page.locator("#statsPanel").is_visible()
    # statsContent renders something (empty message or table)
    page.locator("#statsContent").wait_for(state="visible", timeout=5000)
    content = page.locator("#statsContent")
    assert content.inner_text().strip() != ""


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
    page.get_by_role("button", name="Stats").click()
    page.locator("#statsPanel").wait_for(state="visible", timeout=5000)
    # wait for spinner to disappear and table to appear
    page.locator("#statsContent table").wait_for(state="visible", timeout=5000)
    assert page.locator("#statsContent table").is_visible()
    # at least one data row exists
    assert page.locator("#statsContent tbody tr").count() >= 1
