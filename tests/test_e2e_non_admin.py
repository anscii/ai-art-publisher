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


def test_non_admin_hides_admin_controls(page, live_server):
    _open_editor(page, live_server, False)
    assert page.locator("#editorTitle").is_visible()
    assert page.locator("#generateBtn").is_hidden()
    assert page.locator("#generateFullBtn").is_hidden()
    assert page.locator("#navStats").is_hidden()
    assert page.locator('button[data-bs-target="#settingsModal"]').is_hidden()


def test_admin_shows_admin_controls(page, live_server):
    _open_editor(page, live_server, True)
    page.locator("#generateBtn").wait_for(state="visible")
    assert page.locator("#navStats").is_visible()
