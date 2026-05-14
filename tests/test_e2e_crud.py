import pytest

pytestmark = pytest.mark.e2e


def test_create_series(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()
    assert page.locator("#editorTitle").is_visible()


def test_edit_title(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    title_input = page.locator("#editorTitle")
    title_input.wait_for()
    title_input.fill("E2E Test Series")
    title_input.press("Tab")
    page.locator("#seriesItems").get_by_text("E2E Test Series").wait_for(timeout=5000)
    assert page.locator("#seriesItems").get_by_text("E2E Test Series").is_visible()


def test_delete_series_to_trash(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()
    page.locator("#editorPanel").get_by_title("Delete series").click()
    page.locator("#toastContainer").get_by_text("Moved to Trash").wait_for(timeout=5000)
    assert page.locator("#toastContainer").get_by_text("Moved to Trash").is_visible()
