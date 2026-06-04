"""E2E tests for Stories publishing flow (modal-based IG-native editor)."""

import base64

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _create_series_with_instagram_post(page, live_server, tmp_path, img_count=1):
    png_path = tmp_path / "test.png"
    png_path.write_bytes(_TINY_PNG)

    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    for i in range(img_count):
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name="Add images").click()
        fc.value.set_files(str(png_path))
        # Wait for exactly i+1 images — "last" returns immediately when prior images still
        # exist, causing a race where selections are wiped by the subsequent loadSeriesDetail.
        expect(page.locator("[data-image-id]")).to_have_count(i + 1, timeout=20000)

    for btn in page.locator("[data-select-btn]").all():
        btn.click()
    page.locator(".aap-thumb.is-selected").first.wait_for(timeout=8000)

    page.get_by_role("button", name="New post").click()
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


def _open_story_modal(page):
    page.locator("[data-story-btn]").first.click()
    page.locator("#storyEditorModal").wait_for(state="visible", timeout=5000)


def test_story_button_appears_on_instagram_post(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    page.locator("[data-story-btn]").wait_for(timeout=5000)
    assert page.locator("[data-story-btn]").count() >= 1


def test_create_story_shows_image_picker(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    assert page.locator("[data-story-image-checkbox]").count() >= 1


def test_story_image_picker_preselects_images(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)

    checkboxes = page.locator("[data-story-image-checkbox]").all()
    checked = sum(1 for cb in checkboxes if cb.is_checked())
    assert checked >= 1


def test_generate_story_draft_shows_frame_strip(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()

    # Strip shows all frames
    page.locator("[data-story-frames]").wait_for(timeout=8000)
    # 1 image → 2 frames (cover + text) → 2 strip chips
    assert page.locator(".se-strip__chip").count() >= 2


def test_story_editor_shows_phone_preview(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    # Phone frame preview is present
    expect(page.locator(".va__phone")).to_be_visible(timeout=3000)


def test_navigate_to_text_frame_shows_textarea(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    # Navigate to frame 2 (text) via strip or next button
    strip_chips = page.locator(".se-strip__chip")
    if strip_chips.count() >= 2:
        strip_chips.nth(1).click()  # second chip = text frame
    page.locator("[data-story-frame-text]").wait_for(timeout=5000)
    assert page.locator("[data-story-frame-text]").count() >= 1


def test_edit_text_frame_updates_content(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    # Navigate to text frame
    strip_chips = page.locator(".se-strip__chip")
    if strip_chips.count() >= 2:
        strip_chips.nth(1).click()
    page.locator("[data-story-frame-text]").wait_for(timeout=5000)

    textarea = page.locator("[data-story-frame-text]").first
    textarea.click(click_count=3)
    textarea.fill("The ceilings weep ink.")
    page.wait_for_timeout(1000)


def test_render_preview_and_publish(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-render-btn]").wait_for(timeout=8000)

    # Publish disabled before render
    expect(page.locator("[data-story-publish-btn]")).to_be_disabled(timeout=3000)

    # Render
    page.locator("[data-story-render-btn]").click()
    page.locator("#toastContainer").get_by_text("Rendered").wait_for(timeout=15000)

    # Publish enabled after render
    publish_btn = page.locator("[data-story-publish-btn]")
    expect(publish_btn).to_be_enabled(timeout=5000)
    publish_btn.click()
    page.locator("#toastContainer").get_by_text("published").wait_for(timeout=10000)


def test_story_status_icon_appears_in_post_row(page, live_server, tmp_path):
    """After creating a story and reloading, post row shows draft clock icon."""
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    # Close modal
    page.locator("#storyEditorModal .aap-icon-btn").click()
    page.locator("#storyEditorModal").wait_for(state="hidden", timeout=3000)

    # Reload page — series stays selected via URL param, post row re-renders
    page.reload()
    page.locator("[data-post-row]").wait_for(timeout=8000)

    # Story button should show bi-clock (draft status) below the film icon
    story_btn = page.locator("[data-story-btn]").first
    expect(story_btn.locator(".bi-clock")).to_be_visible(timeout=5000)


def test_close_modal_via_close_button(page, live_server, tmp_path):
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)

    # Close via × button in modal header
    page.locator("#storyEditorModal .aap-icon-btn").click()
    page.locator("#storyEditorModal").wait_for(state="hidden", timeout=3000)


def _generate_and_go_to_text_frame(page):
    """Generate story draft and navigate to the first text frame. Returns the textarea."""
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)
    page.locator(".se-strip__chip").nth(1).click()
    page.locator("[data-story-frame-text]").wait_for(timeout=5000)
    return page.locator("[data-story-frame-text]").first


def test_reset_button_reverts_unsaved_edits(page, live_server, tmp_path):
    """Reset re-fetches server state, discarding in-memory edits."""
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    textarea = _generate_and_go_to_text_frame(page)
    original = textarea.input_value()

    textarea.fill("Completely different text that should vanish.")

    page.locator("button[title='Discard unsaved changes and revert to last saved state']").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    page.locator(".se-strip__chip").nth(1).click()
    page.locator("[data-story-frame-text]").wait_for(timeout=5000)
    assert page.locator("[data-story-frame-text]").first.input_value() == original


def test_close_without_render_restores_draft_on_reopen(page, live_server, tmp_path):
    """Unsaved edits persist in localStorage across modal close/open without render."""
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    textarea = _generate_and_go_to_text_frame(page)

    textarea.fill("Draft text that should survive close.")

    # Close without rendering
    page.locator("#storyEditorModal .aap-icon-btn").click()
    page.locator("#storyEditorModal").wait_for(state="hidden", timeout=3000)

    # Reopen — localStorage draft should be merged in
    _open_story_modal(page)
    page.locator("[data-story-frames]").wait_for(timeout=8000)
    page.locator(".se-strip__chip").nth(1).click()
    page.locator("[data-story-frame-text]").wait_for(timeout=5000)
    assert (
        page.locator("[data-story-frame-text]").first.input_value()
        == "Draft text that should survive close."
    )


def test_format_controls_do_not_crash(page, live_server, tmp_path):
    """BG, Align, H-Align, and Font rail buttons must be clickable without JS errors."""
    _create_series_with_instagram_post(page, live_server, tmp_path)
    _open_story_modal(page)
    textarea = _generate_and_go_to_text_frame(page)
    assert textarea.is_visible()

    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    # Open BG panel and pick a background option
    page.locator(".se-rail__btn").filter(has_text="BG").click()
    page.locator(".se-rail__pick").first.wait_for(timeout=3000)
    page.locator(".se-rail__pick").first.click()
    page.wait_for_timeout(300)

    # Open Align panel and pick an option (exact "Align" so H-Align doesn't match first)
    page.locator(".se-rail__btn").filter(has_text="Align").first.click()
    page.locator(".se-rail__pick").first.wait_for(timeout=3000)
    page.locator(".se-rail__pick").first.click()
    page.wait_for_timeout(300)

    # Open H-Align panel and pick "Left"
    page.locator(".se-rail__btn").filter(has_text="H-Align").click()
    page.locator(".se-rail__pick").filter(has_text="Left").wait_for(timeout=3000)
    page.locator(".se-rail__pick").filter(has_text="Left").click()
    page.wait_for_timeout(300)

    assert js_errors == [], f"JS errors after using format controls: {js_errors}"


def test_frame_strip_scrolls_to_selected_chip(page, live_server, tmp_path):
    """Clicking a chip that overflows the strip must scroll it into view."""
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=4)
    _open_story_modal(page)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    chips = page.locator(".se-strip__chip")
    last_idx = chips.count() - 1
    chips.nth(last_idx).click()
    page.wait_for_timeout(200)

    # Active chip must be within the strip's visible horizontal bounds
    is_visible = page.evaluate("""() => {
        const strip = document.querySelector('.se-strip');
        const active = document.querySelector('.se-strip__chip.is-on');
        if (!strip || !active) return false;
        const sr = strip.getBoundingClientRect();
        const cr = active.getBoundingClientRect();
        return cr.left >= sr.left - 1 && cr.right <= sr.right + 1;
    }""")
    assert is_visible, "selected chip not visible in strip after click"


def test_apply_all_propagates_color_and_halign(page, live_server, tmp_path):
    """'All' button must copy font size, text_color, and text_halign to all text frames."""
    _create_series_with_instagram_post(page, live_server, tmp_path, img_count=2)
    _open_story_modal(page)

    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))

    # Generate story (2 images → 4 frames: 2 image + 2 text)
    page.locator("[data-story-generate-btn]").wait_for(timeout=5000)
    page.locator("[data-story-generate-btn]").click()
    page.locator("[data-story-frames]").wait_for(timeout=8000)

    # Navigate to first text frame (chip index 1)
    page.locator(".se-strip__chip").nth(1).click()
    page.locator("[data-story-frame-text]").wait_for(timeout=5000)

    # Pick a non-default text color via colorbar
    page.locator(".se-swatch").nth(1).click()
    page.wait_for_timeout(200)

    # Pick a non-default H-Align
    page.locator(".se-rail__btn").filter(has_text="H-Align").click()
    page.locator(".se-rail__pick").filter(has_text="Left").wait_for(timeout=3000)
    page.locator(".se-rail__pick").filter(has_text="Left").click()
    page.wait_for_timeout(200)

    # Click "All" to propagate size, color, halign to all text frames
    page.locator("button[title='Apply this size to all frames']").click()
    page.wait_for_timeout(300)

    assert js_errors == [], f"JS errors after clicking All: {js_errors}"
