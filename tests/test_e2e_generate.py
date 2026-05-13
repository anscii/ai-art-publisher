import pytest

pytestmark = pytest.mark.e2e


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
