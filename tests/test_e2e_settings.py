import httpx
import pytest

pytestmark = pytest.mark.e2e

_SETTINGS_BTN = "button[data-bs-target='#settingsModal']"


def _open_settings(page, live_server):
    page.goto(live_server)
    page.locator(_SETTINGS_BTN).click()
    page.locator("#settingsModal").wait_for(state="visible", timeout=5000)


def _api_put(live_server, payload: dict) -> None:
    """Write settings directly to the live server's database via HTTP."""
    httpx.put(f"{live_server}/api/settings", json=payload, timeout=5)


def test_settings_modal_opens(page, live_server):
    _open_settings(page, live_server)
    assert page.locator("#settingsModal").is_visible()


def test_test_connection_shows_result(page, live_server):
    _open_settings(page, live_server)
    # Wait for loadSettings() to finish initialising button states
    page.locator("#settingsModal .aap-secret-row").first.wait_for(state="visible", timeout=3000)

    anthropic_row = page.locator("#settingsModal .aap-secret-row").filter(
        has=page.locator("#s_anthropic_api_key")
    )
    anthropic_row.get_by_role("button", name="Test").click()
    # Any toast proves the Test button wired up correctly (either "not configured" or API error)
    page.locator("#toastContainer .toast").wait_for(timeout=15000)
    assert page.locator("#toastContainer .toast").count() >= 1


def test_save_settings(page, live_server):
    _open_settings(page, live_server)

    page.locator("#s_anthropic_api_key").fill("sk-e2e-test-key")
    page.locator("#settingsModal").get_by_role("button", name="Save").click()
    page.locator("#toastContainer").get_by_text("Settings saved").wait_for(timeout=5000)
    assert page.locator("#toastContainer").get_by_text("Settings saved").is_visible()


def test_unconfigured_keys_show_missing_state(page, live_server):
    """Secret rows show aap-btn-test-missing for keys that are cleared to empty.
    Forces openai_api_key to empty via the live server's API to guarantee state."""
    # Force a known-empty state regardless of what the env bootstrapped
    _api_put(live_server, {"openai_api_key": ""})

    _open_settings(page, live_server)
    # Wait for loadSettings to run (button state set after API response)
    page.wait_for_timeout(800)

    openai_row = page.locator("#settingsModal .aap-secret-row").filter(
        has=page.locator("#s_openai_api_key")
    )
    test_btn = openai_row.get_by_role("button", name="Test")
    classes = test_btn.get_attribute("class") or ""
    assert "aap-btn-test-missing" in classes


def test_configured_key_shows_ok_state(page, live_server):
    """After saving a key via the live server's API, loadSettings marks the button aap-btn-test-ok."""
    # Write via the live server so the browser sees the same DB
    _api_put(live_server, {"google_api_key": "sk-google-fake-for-test"})

    _open_settings(page, live_server)
    # Wait for loadSettings to run
    page.wait_for_timeout(800)

    google_row = page.locator("#settingsModal .aap-secret-row").filter(
        has=page.locator("#s_google_api_key")
    )
    test_btn = google_row.get_by_role("button", name="✓ Tested")
    classes = test_btn.get_attribute("class") or ""
    assert "aap-btn-test-ok" in classes
