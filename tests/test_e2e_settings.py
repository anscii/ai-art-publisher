import httpx
import pytest

pytestmark = pytest.mark.e2e

_SETTINGS_BTN = "button[data-bs-target='#settingsModal']"


def _open_settings(page, live_server):
    page.goto(live_server)
    page.locator(_SETTINGS_BTN).click()
    page.locator("#settingsModal").wait_for(state="visible", timeout=5000)


def _api_put(live_server, payload: dict) -> None:
    """Write the caller's AI settings directly to the live server's database via HTTP."""
    httpx.put(f"{live_server}/api/me/settings", json=payload, timeout=5)


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


def test_model_field_accepts_free_text(page, live_server):
    """Model pickers are <input list=datalist>: a custom model id saves and reloads."""
    _open_settings(page, live_server)
    model = page.locator("#s_openrouter_default_model")
    assert model.evaluate("el => el.tagName") == "INPUT"
    model.fill("vendor/custom-model-x")
    page.locator("#settingsModal").get_by_role("button", name="Save").click()
    page.locator("#toastContainer").get_by_text("Settings saved").wait_for(timeout=5000)

    _open_settings(page, live_server)
    page.wait_for_function(
        "() => document.getElementById('s_openrouter_default_model').value === 'vendor/custom-model-x'",
        timeout=5000,
    )


def test_my_openrouter_key_not_overwritten_by_instance_key(page, live_server):
    """Admin view: the instance (Default AI Access) OpenRouter key must not show in My AI."""
    httpx.put(f"{live_server}/api/settings", json={"openrouter_api_key": "sk-instance"}, timeout=5)
    _api_put(live_server, {"openrouter_api_key": ""})

    _open_settings(page, live_server)
    page.wait_for_function(
        "() => document.querySelector('#s_r2_endpoint').dataset.loaded !== undefined"
    )
    assert page.locator("#s_openrouter_api_key").input_value() == ""


def test_clearing_saved_key_removes_it(page, live_server):
    _api_put(live_server, {"deepseek_api_key": "sk-deepseek-fake"})

    _open_settings(page, live_server)
    key = page.locator("#s_deepseek_api_key")
    page.wait_for_function("() => document.querySelector('#s_deepseek_api_key').value === '****'")
    key.fill("")
    page.locator("#settingsModal").get_by_role("button", name="Save").click()
    page.locator("#toastContainer").get_by_text("Settings saved").wait_for(timeout=5000)

    assert httpx.get(f"{live_server}/api/me/settings", timeout=5).json()["deepseek_api_key"] == ""
