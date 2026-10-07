import json

import pytest

pytestmark = pytest.mark.e2e


def _open_editor(page, live_server, is_admin):
    page.route(
        "**/api/me",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"email": "f@x", "is_admin": is_admin}),
        ),
    )
    page.goto(live_server)
    page.get_by_role("button", name="New series").click()
    page.locator("#editorTitle").wait_for()


_INSTANCE = "#settingsModal .admin-only"


def test_non_admin_sees_ai_but_not_instance_settings(page, live_server):
    _open_editor(page, live_server, False)
    assert page.locator("#editorTitle").is_visible()
    assert page.locator("#generateBtn").is_visible()
    assert page.locator("#generateFullBtn").is_visible()
    assert page.locator("#navStats").is_visible()
    page.locator('button[data-bs-target="#settingsModal"]').click()
    page.locator("#settingsModal").wait_for(state="visible")
    assert page.locator("#s_anthropic_api_key").is_visible()
    assert page.locator(_INSTANCE).is_hidden()


def test_admin_sees_instance_settings(page, live_server):
    _open_editor(page, live_server, True)
    page.locator("#generateBtn").wait_for(state="visible")
    assert page.locator("#navStats").is_visible()
    page.locator('button[data-bs-target="#settingsModal"]').click()
    page.locator("#settingsModal").wait_for(state="visible")
    assert page.locator(_INSTANCE).is_visible()
