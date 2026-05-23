import pytest

pytestmark = pytest.mark.e2e

_QUEUE_BTN = "#navQueue"
_QUEUE_PANEL = "#queuePanel"


def test_queue_panel_opens(page, live_server):
    page.goto(live_server)
    page.locator(_QUEUE_BTN).click()
    page.locator(_QUEUE_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(_QUEUE_PANEL).is_visible()


def test_queue_panel_shows_aap_page_chrome(page, live_server):
    """Queue panel renders the AAP page chrome: icon tile + title + kicker."""
    page.goto(live_server)
    page.locator(_QUEUE_BTN).click()
    page.locator(_QUEUE_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(f"{_QUEUE_PANEL} .aap-page__title").is_visible()
    assert page.locator(f"{_QUEUE_PANEL} .aap-page__icon").is_visible()


def test_queue_empty_or_table(page, live_server):
    """Queue panel renders either an .aap-table or the empty-state paragraph."""
    page.goto(live_server)
    page.locator(_QUEUE_BTN).click()
    page.locator(_QUEUE_PANEL).wait_for(state="visible", timeout=5000)
    # Wait for async fetch to settle
    page.wait_for_timeout(800)
    has_table = page.locator(f"{_QUEUE_PANEL} .aap-table").count() > 0
    has_empty = page.locator(f"{_QUEUE_PANEL} #queueContent p").count() > 0
    assert has_table or has_empty
