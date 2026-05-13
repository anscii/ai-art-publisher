import base64

import pytest

pytestmark = pytest.mark.e2e

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _create_series_with_selected_image(page, live_server, tmp_path):
    png_path = tmp_path / "test.png"
    png_path.write_bytes(_TINY_PNG)

    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    with page.expect_file_chooser() as fc:
        page.get_by_role("button", name="Add").click()
    fc.value.set_files(str(png_path))

    page.locator("#imageStrip [data-image-id]").wait_for(timeout=10000)
    page.locator("[data-select-btn]").first.click()
    page.locator(".thumb-selected").wait_for(timeout=3000)


def test_post_telegram_fake(page, live_server, tmp_path):
    _create_series_with_selected_image(page, live_server, tmp_path)
    page.get_by_role("button", name="Telegram").click()
    page.locator("#confirmModal").wait_for(state="visible", timeout=3000)
    page.locator("#confirmOkBtn").click()
    page.locator("#toastContainer").get_by_text("[FAKE] Posted to telegram").wait_for(timeout=10000)


def test_schedule_series(page, live_server, tmp_path):
    _create_series_with_selected_image(page, live_server, tmp_path)
    page.locator("#schedDate").fill("2099-12-31T12:00")
    page.locator("#schedTg").check()
    page.get_by_role("button", name="Schedule").click()
    page.locator("#toastContainer").get_by_text("Scheduled").wait_for(timeout=5000)
    assert page.locator("#schedResult").get_by_text("Scheduled for").is_visible()


def test_cancel_schedule(page, live_server, tmp_path):
    _create_series_with_selected_image(page, live_server, tmp_path)
    page.locator("#schedDate").fill("2099-12-31T12:00")
    page.locator("#schedTg").check()
    page.get_by_role("button", name="Schedule").click()
    page.locator("#toastContainer").get_by_text("Scheduled").wait_for(timeout=5000)
    # Re-click the sidebar item to re-render editor with updated series.status='scheduled'
    page.locator("#seriesItems [id^='si-']").first.click()
    page.get_by_role("button", name="Cancel").wait_for(timeout=5000)
    page.get_by_role("button", name="Cancel").click()
    page.locator("#confirmModal").wait_for(state="visible", timeout=3000)
    page.locator("#confirmOkBtn").click()
    page.locator("#toastContainer").get_by_text("Schedule cancelled").wait_for(timeout=5000)
