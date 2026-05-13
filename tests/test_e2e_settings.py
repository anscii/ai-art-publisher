import pytest

pytestmark = pytest.mark.e2e

_SETTINGS_BTN = "button[data-bs-target='#settingsModal']"


def test_settings_modal_opens(page, live_server):
    page.goto(live_server)
    page.locator(_SETTINGS_BTN).click()
    page.locator("#settingsModal").wait_for(state="visible", timeout=5000)
    assert page.locator("#settingsModal").is_visible()


def test_test_connection_shows_result(page, live_server):
    page.goto(live_server)
    page.locator(_SETTINGS_BTN).click()
    page.locator("#settingsModal").wait_for(state="visible", timeout=5000)

    anthropic_group = page.locator("#settingsModal .input-group").filter(
        has=page.locator("#s_anthropic_api_key")
    )
    anthropic_group.get_by_role("button", name="Test").click()
    # Any toast proves the Test button wired up correctly (either "not configured" or API error)
    page.locator("#toastContainer .toast").wait_for(timeout=15000)
    assert page.locator("#toastContainer .toast").count() >= 1


def test_save_settings(page, live_server):
    page.goto(live_server)
    page.locator(_SETTINGS_BTN).click()
    page.locator("#settingsModal").wait_for(state="visible", timeout=5000)

    page.locator("#s_anthropic_api_key").fill("sk-e2e-test-key")
    page.locator("#settingsModal").get_by_role("button", name="Save").click()
    page.locator("#toastContainer").get_by_text("Settings saved").wait_for(timeout=5000)
    assert page.locator("#toastContainer").get_by_text("Settings saved").is_visible()
