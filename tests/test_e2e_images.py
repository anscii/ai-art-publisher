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

    # Images render in libraryGrid (unselected) or selectedTray (selected)
    page.locator("[data-image-id]").wait_for(timeout=10000)
    return page


def test_upload_image(series_with_image):
    assert series_with_image.locator("[data-image-id]").count() >= 1


def test_select_image(series_with_image):
    page = series_with_image
    page.locator("[data-select-btn]").first.click()
    page.locator(".aap-thumb.is-selected").wait_for(timeout=3000)
    assert page.locator(".aap-thumb.is-selected").count() >= 1


def test_lightbox_opens(series_with_image):
    page = series_with_image
    page.locator(".aap-thumb img").first.click()
    page.locator("#lightboxModal").wait_for(state="visible", timeout=5000)
    assert page.locator("#lightboxImg").is_visible()


def test_lightbox_shows_counter(series_with_image):
    page = series_with_image
    page.locator(".aap-thumb img").first.click()
    page.locator("#lightboxModal").wait_for(state="visible", timeout=5000)
    assert "1" in page.locator("#lightboxCounter").inner_text()


def test_lightbox_close(series_with_image):
    page = series_with_image
    page.locator(".aap-thumb img").first.click()
    page.locator("#lightboxModal").wait_for(state="visible", timeout=5000)
    page.locator("#lightboxClose").click()
    page.locator("#lightboxModal").wait_for(state="hidden", timeout=5000)
    assert not page.locator("#lightboxModal").is_visible()
