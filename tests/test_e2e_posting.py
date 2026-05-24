import base64

import pytest

pytestmark = pytest.mark.e2e

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _create_series_with_post(page, live_server, tmp_path, platform="telegram"):
    """Create a series, upload an image, select it, open New post form, save a draft post."""
    png_path = tmp_path / "test.png"
    png_path.write_bytes(_TINY_PNG)

    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    with page.expect_file_chooser() as fc:
        page.get_by_role("button", name="Add images").click()
    fc.value.set_files(str(png_path))

    page.locator("[data-image-id]").wait_for(timeout=20000)
    # Select the image
    page.locator("[data-select-btn]").first.click()
    page.locator(".aap-thumb.is-selected").wait_for(timeout=8000)

    # Open "New post" form
    page.get_by_role("button", name="New post").click()

    _plat_ids = {"telegram": "pf_tg", "instagram": "pf_ig", "pinterest": "pf_pt"}
    # Uncheck all platforms, then check only the desired one
    for plat in ["telegram", "instagram", "pinterest"]:
        cb = page.locator(f"#{_plat_ids[plat]}")
        if plat == platform:
            if not cb.is_checked():
                cb.check()
        else:
            if cb.is_checked():
                cb.uncheck()

    page.locator("#pf_title").fill("Test post")
    page.get_by_role("button", name="Save post(s)").click()

    # Wait for post row to appear in Posts section
    page.locator("[data-post-row]").wait_for(timeout=8000)


def test_post_telegram_fake(page, live_server, tmp_path):
    _create_series_with_post(page, live_server, tmp_path, platform="telegram")
    # Click post-now button (send icon) on the first post row
    page.locator("button[title='Post now']").first.click()
    page.locator("#confirmModal").wait_for(state="visible", timeout=3000)
    page.locator("#confirmOkBtn").click()
    page.locator("#toastContainer").get_by_text("[FAKE] Posted to telegram").wait_for(timeout=10000)


def test_schedule_series(page, live_server, tmp_path):
    _create_series_with_post(page, live_server, tmp_path, platform="telegram")
    # Click schedule button on the post row
    page.locator("button[title='Schedule']").first.click()
    # Inline picker appears — fill datetime and click Schedule
    page.locator("input[type='datetime-local']").last.fill("2099-12-31T12:00")
    page.locator("button:has-text('Schedule')").last.click()
    page.locator("#toastContainer").get_by_text("Scheduled").wait_for(timeout=5000)


def test_cancel_schedule(page, live_server, tmp_path):
    _create_series_with_post(page, live_server, tmp_path, platform="telegram")
    # Schedule the post
    page.locator("button[title='Schedule']").first.click()
    page.locator("input[type='datetime-local']").last.fill("2099-12-31T12:00")
    page.locator("button:has-text('Schedule')").last.click()
    page.locator("#toastContainer").get_by_text("Scheduled").wait_for(timeout=5000)
    # Reload to see updated post status, then cancel
    page.wait_for_timeout(500)
    page.locator("button[title='Cancel schedule']").wait_for(timeout=5000)
    page.locator("button[title='Cancel schedule']").click()
    page.locator("#confirmModal").wait_for(state="visible", timeout=3000)
    page.locator("#confirmOkBtn").click()
    page.locator("#toastContainer").get_by_text("Schedule cancelled").wait_for(timeout=5000)
