"""E2E: Undo toast for AI variant deletion."""

import json

import pytest

pytestmark = pytest.mark.e2e


def _create_series_with_variant(page, live_server):
    import time

    r = page.request.post(
        f"{live_server}/api/series",
        data=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    series_id = r.json()["id"]

    r = page.request.post(
        f"{live_server}/api/series/{series_id}/generate",
        data=json.dumps({"hint": "test hint"}),
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    # Generation runs in background — poll status endpoint until settled (HTTP 200).
    for _ in range(20):
        sr = page.request.get(f"{live_server}/api/series/{series_id}/generation-status")
        if sr.status == 200:
            break
        time.sleep(0.3)
    r2 = page.request.get(f"{live_server}/api/series/{series_id}")
    assert r2.ok, r2.text()
    variants = r2.json()["ai_variants"]
    assert variants, "FAKE_AI should produce at least one variant"
    return series_id, variants[0]["id"]


def _open_series(page, live_server, series_id):
    page.goto(live_server)
    page.wait_for_function("() => typeof selectSeries === 'function'", timeout=10000)
    page.evaluate(f"selectSeries('{series_id}')")
    page.locator(f"#descBody-{series_id}").wait_for(state="visible", timeout=5000)


def test_delete_variant_shows_undo_toast(page, live_server):
    """Clicking × on a variant pill immediately hides it and shows an undo toast."""
    series_id, _ = _create_series_with_variant(page, live_server)
    _open_series(page, live_server, series_id)

    pill = page.locator(".aap-variant").first
    pill.wait_for(state="visible", timeout=5000)
    pill.locator(".aap-variant__x").click()

    page.locator(".aap-variant").wait_for(state="hidden", timeout=3000)
    page.locator("[data-undo-toast]").wait_for(state="visible", timeout=3000)


def test_undo_variant_deletion_restores_variant(page, live_server):
    """Clicking Undo in the undo toast restores the variant pill."""
    series_id, _ = _create_series_with_variant(page, live_server)
    _open_series(page, live_server, series_id)

    pill = page.locator(".aap-variant").first
    pill.wait_for(state="visible", timeout=5000)
    pill.locator(".aap-variant__x").click()

    page.locator("[data-undo-toast]").wait_for(state="visible", timeout=3000)
    page.locator("[data-undo-toast]").click()

    page.locator(".aap-variant").wait_for(state="visible", timeout=3000)
