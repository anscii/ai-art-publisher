import pytest

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
