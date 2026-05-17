"""E2E: view post content modal."""

import json

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture
def series_with_post(page, live_server):
    """Create series + draft post via API, navigate to series in UI."""
    r = page.request.post(
        f"{live_server}/api/series",
        data=json.dumps({}),
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()
    series_id = r.json()["id"]

    r = page.request.post(
        f"{live_server}/api/series/{series_id}/posts",
        data=json.dumps(
            {
                "platforms": ["telegram"],
                "title": "E2E Post Title",
                "description_telegram": "This is the caption for E2E testing.",
                "description_other": "This is the caption for E2E testing.",
                "image_ids": [],
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert r.ok, r.text()

    page.goto(live_server)
    # Bypass sidebar click (series may not be on page 1 of list).
    # Wait for app JS to load, then select series directly.
    page.wait_for_function("() => typeof selectSeries === 'function'", timeout=10000)
    page.evaluate(f"selectSeries('{series_id}')")
    page.locator("[data-post-row]").wait_for(timeout=5000)
    return series_id


def test_post_view_modal_opens(series_with_post, page):
    """Eye button on post row opens modal."""
    page.locator('button[title="View post content"]').first.click()
    page.locator("#postViewModal").wait_for(state="visible", timeout=3000)
    assert page.locator("#postViewModal").is_visible()


def test_post_view_modal_shows_title(series_with_post, page):
    """View modal shows the post title."""
    page.locator('button[title="View post content"]').first.click()
    page.locator("#postViewModal").wait_for(state="visible", timeout=3000)
    assert "E2E Post Title" in page.locator("#postViewBody").inner_text()


def test_post_view_modal_shows_caption(series_with_post, page):
    """View modal shows the post description."""
    page.locator('button[title="View post content"]').first.click()
    page.locator("#postViewModal").wait_for(state="visible", timeout=3000)
    assert "This is the caption for E2E testing." in page.locator("#postViewBody").inner_text()
