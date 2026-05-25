"""E2E: view post content modal."""

import json

import pytest

pytestmark = pytest.mark.e2e

# Minimal post skeleton accepted by showPostContent(); only fields it touches.
_BASE_POST = {
    "platform": "instagram",
    "status": "posted",
    "title": "Link Test Post",
    "title_ru": None,
    "description": "Caption text.",
    "tags": [],
    "collection_line": None,
    "collection_line_ru": None,
    "posted_at": "2026-05-25T12:00:00Z",
    "scheduled_at": None,
    "external_post_id": None,
    "post_url": None,
    "error_message": None,
    "image_ids": [],
    "seo": None,
}


def _show_post(page, overrides: dict) -> None:
    """Invoke showPostContent() with a mock post; waits for modal to be visible."""
    post = {**_BASE_POST, **overrides}
    # showPostContent(post, imgMap, series)
    page.evaluate(
        "([post]) => showPostContent(post, {}, {images: []})",
        [post],
    )
    page.locator("#postViewModal").wait_for(state="visible", timeout=3000)


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


# ── Platform link rendering (AIRT-38) ─────────────────────────────────────────


@pytest.fixture
def app_loaded(page, live_server):
    """Navigate to app and wait for JS to initialise."""
    page.goto(live_server)
    page.wait_for_function("() => typeof showPostContent === 'function'", timeout=10000)


def test_instagram_post_url_shown_as_link(app_loaded, page):
    """post_url from DB (the real permalink) is used for the Instagram link, not external_post_id."""
    permalink = "https://www.instagram.com/p/AbCdEfG/"
    _show_post(
        page,
        {
            "platform": "instagram",
            "post_url": permalink,
            "external_post_id": "12345678901234567",  # numeric media ID — must NOT appear in href
        },
    )
    link = page.locator("#postViewBody a[href]").first
    assert link.get_attribute("href") == permalink


def test_telegram_post_url_shown_as_link(app_loaded, page):
    """Telegram posts with a post_url display a 'View on telegram' link."""
    tme_url = "https://t.me/mychannel/99"
    _show_post(
        page,
        {
            "platform": "telegram",
            "post_url": tme_url,
            "external_post_id": None,
        },
    )
    link = page.locator("#postViewBody a[href]").first
    assert link.get_attribute("href") == tme_url


def test_instagram_no_link_without_post_url(app_loaded, page):
    """When post_url is absent (e.g. permalink fetch failed), no link is rendered.

    Previously this would construct a broken URL from the numeric media ID.
    """
    _show_post(
        page,
        {
            "platform": "instagram",
            "post_url": None,
            "external_post_id": "12345678901234567",
        },
    )
    # No anchor should appear in the body for a broken/absent URL.
    assert page.locator("#postViewBody a[href]").count() == 0


def test_facebook_fallback_link_still_works(app_loaded, page):
    """Facebook posts without post_url fall back to the constructed facebook.com URL."""
    fb_id = "some_fb_post_id"
    _show_post(
        page,
        {
            "platform": "facebook",
            "post_url": None,
            "external_post_id": fb_id,
        },
    )
    link = page.locator("#postViewBody a[href]").first
    assert link.get_attribute("href") == f"https://www.facebook.com/{fb_id}"
