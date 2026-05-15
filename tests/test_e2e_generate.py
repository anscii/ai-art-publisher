import base64

import pytest

pytestmark = pytest.mark.e2e

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_generate_descriptions(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    page.locator("#genHint").fill("A fox spirit in a rain-soaked library")
    page.locator("#generateBtn").click()

    page.locator("#toastContainer").get_by_text("Generated new variants").wait_for(timeout=15000)
    assert page.locator("#toastContainer").get_by_text("Generated new variants").is_visible()


def test_generate_fills_description_field(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    page.locator("#genHint").fill("Dark academia gothic horror")
    page.locator("#generateBtn").click()

    page.locator("#toastContainer").get_by_text("Generated new variants").wait_for(timeout=15000)
    desc_en = page.locator("#f_desc_en").input_value()
    assert desc_en


def test_generate_preserves_image_selection(page, live_server, tmp_path):
    png1 = tmp_path / "img1.png"
    png2 = tmp_path / "img2.png"
    png1.write_bytes(_TINY_PNG)
    png2.write_bytes(_TINY_PNG)

    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    for png in (png1, png2):
        with page.expect_file_chooser() as fc:
            page.get_by_role("button", name="Add").click()
        fc.value.set_files(str(png))
        page.locator("#imageStrip [data-image-id]").nth(0 if png is png1 else 1).wait_for(
            timeout=10000
        )

    thumbs = page.locator("#imageStrip [data-image-id]")
    assert thumbs.count() == 2

    # select only the second image
    second_id = thumbs.nth(1).get_attribute("data-image-id")
    page.locator(f'[data-select-btn="{second_id}"]').click()
    page.locator(".thumb-selected").wait_for(timeout=3000)

    page.locator("#genHint").fill("A fox spirit")
    page.locator("#generateBtn").click()
    page.locator("#toastContainer").get_by_text("Generated new variants").wait_for(timeout=15000)

    # selected image must still be selected and first in strip
    assert page.locator(".thumb-selected").count() >= 1
    first_id = page.locator("#imageStrip [data-image-id]").first.get_attribute("data-image-id")
    assert first_id == second_id


def test_reset_to_saved_restores_fields(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    page.locator("#genHint").fill("A ghost in a clockwork city")
    page.locator("#generateBtn").click()
    page.locator("#toastContainer").get_by_text("Generated new variants").wait_for(timeout=15000)

    page.locator("button", has_text="Save").first.click()
    page.locator("#toastContainer").get_by_text("Saved").wait_for(timeout=5000)

    saved_en = page.locator("#f_desc_en").input_value()

    page.locator("#f_desc_en").fill("DIRTY VALUE")
    assert page.locator("#f_desc_en").input_value() == "DIRTY VALUE"

    page.get_by_role("button", name="Reset").click()

    assert page.locator("#f_desc_en").input_value() == saved_en
