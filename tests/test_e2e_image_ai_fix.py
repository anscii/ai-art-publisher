"""
E2E tests for the Fix with AI flow.

These tests cover the two bugs that unit tests cannot catch:
- App.currentSeries not updated after Keep → new image unclickable
- Lightbox filmstrip missing new image after Keep
"""

import base64

import pytest

pytestmark = pytest.mark.e2e

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def series_with_image(page, live_server, tmp_path):
    png_path = tmp_path / "test.png"
    png_path.write_bytes(_TINY_PNG)

    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    with page.expect_file_chooser() as fc:
        page.get_by_role("button", name="Add images").click()
    fc.value.set_files(str(png_path))

    page.locator("[data-image-id]").wait_for(timeout=10000)
    return page


def _do_ai_fix_keep(page):
    """Open the AI fix modal via the thumbnail dropdown and click Keep."""
    page.locator(".aap-thumb .dropdown button").first.click()
    page.get_by_text("Fix with AI").first.click()
    page.locator("#aiFixModal").wait_for(state="visible", timeout=5000)

    page.locator("#aiFixHint").fill("make it darker")
    page.locator("#aiFixSubmitBtn").click()

    # Wait for the preview to appear (FAKE_AI mode is synchronous)
    page.locator("#aiFixPreview:not(.d-none)").wait_for(timeout=10000)

    page.locator("#aiFixKeepBtn").click()
    page.locator("#aiFixModal").wait_for(state="hidden", timeout=10000)


def test_kept_image_appears_in_gallery(series_with_image):
    page = series_with_image
    _do_ai_fix_keep(page)

    # Both original and AI-fixed image should now be in the grid
    page.locator("[data-image-id]").nth(1).wait_for(timeout=5000)
    assert page.locator("[data-image-id]").count() == 2


def test_kept_image_opens_lightbox_on_click(series_with_image):
    """Regression: App.currentSeries not updated → new image click silently failed."""
    page = series_with_image
    _do_ai_fix_keep(page)

    page.locator("[data-image-id]").nth(1).wait_for(timeout=5000)

    # Click the new (second) image thumbnail
    page.locator(".aap-thumb img").nth(1).click()
    page.locator("#lightboxModal").wait_for(state="visible", timeout=5000)
    assert page.locator("#lightboxImg").is_visible()


def test_lightbox_filmstrip_includes_new_image(series_with_image):
    """Regression: filmstrip populated from stale App.currentSeries → new image missing."""
    page = series_with_image
    _do_ai_fix_keep(page)

    page.locator("[data-image-id]").nth(1).wait_for(timeout=5000)

    # Open lightbox on first image, navigate right — should reach image 2
    page.locator(".aap-thumb img").first.click()
    page.locator("#lightboxModal").wait_for(state="visible", timeout=5000)

    page.locator("#lightboxNext").click()
    page.wait_for_timeout(300)

    counter = page.locator("#lightboxCounter").inner_text()
    assert "2" in counter


def test_lightbox_button_opens_fix_modal(series_with_image):
    """Fix with AI button in lightbox closes lightbox and opens fix modal."""
    page = series_with_image

    page.locator(".aap-thumb img").first.click()
    page.locator("#lightboxModal").wait_for(state="visible", timeout=5000)

    page.locator("#lightboxFixAiBtn").click()
    page.locator("#lightboxModal").wait_for(state="hidden", timeout=5000)
    page.locator("#aiFixModal").wait_for(state="visible", timeout=5000)

    assert page.locator("#aiFixHint").is_visible()
