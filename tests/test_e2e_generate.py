import base64

import pytest

pytestmark = pytest.mark.e2e

_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_generate_drafts(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    page.locator("#genHint").fill("A fox spirit in a rain-soaked library")
    page.locator("#generateBtn").click()

    page.locator("#toastContainer").get_by_text("drafts").wait_for(timeout=15000)
    assert page.locator("#toastContainer").get_by_text("drafts").is_visible()


def test_generate_drafts_then_apply_fills_description_field(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    page.locator("#genHint").fill("Dark academia gothic horror")
    page.locator("#generateBtn").click()

    page.locator("#toastContainer").get_by_text("drafts").wait_for(timeout=15000)

    # Click the first draft variant to load its description_en
    page.locator("[data-variant-idx]").first.click()
    desc_en = page.locator("#f_desc_en").input_value()
    assert desc_en


def test_generate_full_fills_all_fields(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    page.locator("#genHint").fill("A ghost in a clockwork city")
    page.locator("#generateBtn").click()
    page.locator("#toastContainer").get_by_text("drafts").wait_for(timeout=15000)

    # Apply a draft
    page.locator("[data-variant-idx]").first.click()
    assert page.locator("#f_desc_en").input_value()

    # Generate full content from the applied draft
    page.locator("#generateFullBtn").click()
    page.locator("#toastContainer").get_by_text("Full content generated").wait_for(timeout=15000)

    # All fields should now be filled
    assert page.locator("#f_pub_title").input_value()
    assert page.locator("#f_desc_en").input_value()
    assert page.locator("#f_desc_ru").input_value()


def test_generate_full_from_manually_typed_description(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    # Type a description manually without generating drafts
    page.locator("#f_desc_en").fill("A manually typed description about something strange.")

    page.locator("#generateFullBtn").click()
    page.locator("#toastContainer").get_by_text("Full content generated").wait_for(timeout=15000)

    assert page.locator("#f_pub_title").input_value()
    assert page.locator("#f_desc_ru").input_value()


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
    page.locator("#toastContainer").get_by_text("drafts").wait_for(timeout=15000)

    # selected image must still be selected and first in strip
    assert page.locator(".thumb-selected").count() >= 1
    first_id = page.locator("#imageStrip [data-image-id]").first.get_attribute("data-image-id")
    assert first_id == second_id


def test_variant_delete_button_hidden_when_used_in_post(page, live_server):
    r = page.request.post(
        f"{live_server}/api/series",
        data="{}",
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    series_id = r.json()["id"]

    r = page.request.post(
        f"{live_server}/api/series/{series_id}/generate",
        data='{"hint": "test"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    variants = r.json()
    assert len(variants) >= 2
    vid = variants[0]["id"]

    r = page.request.put(
        f"{live_server}/api/series/{series_id}",
        data=f'{{"chosen_variant_id": "{vid}"}}',
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()

    r = page.request.post(
        f"{live_server}/api/series/{series_id}/posts",
        data='{"platforms": ["telegram"], "title": "T", "description_telegram": "d", "description_other": "d", "image_ids": []}',
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()

    page.goto(live_server)
    page.wait_for_function("() => typeof selectSeries === 'function'", timeout=10000)
    page.evaluate(f"selectSeries('{series_id}')")
    page.locator("[data-variant-idx]").first.wait_for(timeout=5000)

    del_btns = page.locator('button[title="Delete variant"]')
    first_style = del_btns.nth(0).get_attribute("style") or ""
    assert "display:none" in first_style or "display: none" in first_style
    assert del_btns.nth(1).is_visible()


def test_reset_to_saved_restores_fields(page, live_server):
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()

    page.locator("#genHint").fill("A ghost in a clockwork city")
    page.locator("#generateBtn").click()
    page.locator("#toastContainer").get_by_text("drafts").wait_for(timeout=15000)

    # Apply draft then generate full to get desc_en filled
    page.locator("[data-variant-idx]").first.click()
    page.locator("#generateFullBtn").click()
    page.locator("#toastContainer").get_by_text("Full content generated").wait_for(timeout=15000)

    page.locator("button", has_text="Save").first.click()
    page.locator("#toastContainer").get_by_text("Saved").wait_for(timeout=5000)

    saved_en = page.locator("#f_desc_en").input_value()

    page.locator("#f_desc_en").fill("DIRTY VALUE")
    assert page.locator("#f_desc_en").input_value() == "DIRTY VALUE"

    page.get_by_role("button", name="Reset").click()

    assert page.locator("#f_desc_en").input_value() == saved_en
