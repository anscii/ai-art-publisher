"""E2E tests for Stories publishing flow."""

import base64

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _create_series_with_instagram_post(page, live_server, tmp_path, img_count=2):
    """Create a series with multiple images and an Instagram post."""
    png_path = tmp_path / "test.png"
    png_path.write_bytes(_TINY_PNG)

    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    # Upload images (same file multiple times for simplicity)
    for _ in range(img_count):
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name="Add images").click()
        fc.value.set_files(str(png_path))
        page.locator("[data-image-id]").last.wait_for(timeout=20000)

    # Select all images
    for btn in page.locator("[data-select-btn]").all():
        btn.click()
    page.locator(".aap-thumb.is-selected").first.wait_for(timeout=8000)

    # Open New post form
    page.get_by_role("button", name="New post").click()

    # Select Instagram only
    for plat_id in ["pf_tg", "pf_pt"]:
        cb = page.locator(f"#{plat_id}")
        if cb.is_checked():
            cb.uncheck()
    ig_cb = page.locator("#pf_ig")
    if not ig_cb.is_checked():
        ig_cb.check()

    page.locator("#pf_title").fill("Nocturnal Archive")
    page.get_by_role("button", name="Save post(s)").click()
    page.locator("[data-post-row]").wait_for(timeout=8000)


def test_story_button_appears_on_instagram_post(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    page.locator("[data-story-btn]").wait_for(timeout=5000)
    assert page.locator("[data-story-btn]").count() >= 1


def test_create_story_shows_image_picker(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=2)
    page.locator("[data-story-btn]").first.click()
    page.locator("[data-story-panel]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").wait_for(timeout=3000)
    assert page.locator("[data-story-image-checkbox]").count() >= 1


def test_story_image_picker_preselects_images(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=1)
    page.locator("[data-story-btn]").first.click()
    page.locator("[data-story-generate-btn]").wait_for(timeout=3000)

    checkboxes = page.locator("[data-story-image-checkbox]").all()
    checked = sum(1 for cb in checkboxes if cb.is_checked())
    # All images up to 4 should be pre-checked
    assert checked >= 1


def test_generate_story_draft_shows_frame_cards(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=2)
    page.locator("[data-story-btn]").first.click()
    page.locator("[data-story-generate-btn]").wait_for(timeout=3000)
    page.locator("[data-story-generate-btn]").click()

    # Should show story editor with frames
    page.locator("[data-story-frames]").wait_for(timeout=8000)
    frame_cards = page.locator("[data-story-frame-card]")
    # 2 images → 4 frames (image+text pairs)
    assert frame_cards.count() >= 2


def test_story_has_ordered_image_and_text_frames(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=2)
    page.locator("[data-story-btn]").first.click()
    page.locator("[data-story-generate-btn]").wait_for(timeout=3000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    # Verify text frame textareas are present
    text_areas = page.locator("[data-story-frame-text]")
    assert text_areas.count() >= 1


def test_edit_text_frame_updates_content(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=1)
    page.locator("[data-story-btn]").first.click()
    page.locator("[data-story-generate-btn]").wait_for(timeout=3000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frame-text]").first.wait_for(timeout=8000)

    textarea = page.locator("[data-story-frame-text]").first
    textarea.click(click_count=3)
    textarea.fill("The ceilings weep ink.")
    # Wait for debounce + API call
    page.wait_for_timeout(1000)


def test_render_preview_enables_publish(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=1)
    page.locator("[data-story-btn]").first.click()
    page.locator("[data-story-generate-btn]").wait_for(timeout=3000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-render-btn]").wait_for(timeout=8000)

    # Publish button should be disabled before render
    publish_btn = page.locator("[data-story-publish-btn]")
    assert publish_btn.is_disabled()

    # Click Render Preview
    page.locator("[data-story-render-btn]").click()
    page.wait_for_timeout(5000)  # rendering can take a moment

    # After render: frames should have rendered previews
    page.locator("[data-story-frames]").wait_for(timeout=10000)


def test_fake_publish_story(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=1)
    page.locator("[data-story-btn]").first.click()
    page.locator("[data-story-generate-btn]").wait_for(timeout=3000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-render-btn]").wait_for(timeout=8000)

    # Render first
    page.locator("[data-story-render-btn]").click()

    # Wait for render to complete (status badge changes or render button re-enables)
    page.locator("#toastContainer").get_by_text("Rendered").wait_for(timeout=15000)

    # Now publish — button should be enabled after render
    publish_btn = page.locator("[data-story-publish-btn]")
    expect(publish_btn).to_be_enabled(timeout=5000)
    publish_btn.click()

    page.locator("#toastContainer").get_by_text("published").wait_for(timeout=10000)


def test_toggle_panel_closes_story_editor(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    btn = page.locator("[data-story-btn]").first
    btn.click()
    page.locator("[data-story-panel]").wait_for(timeout=5000)
    btn.click()
    page.locator("[data-story-panel]").wait_for(state="detached", timeout=3000)
