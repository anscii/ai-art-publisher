import pytest

pytestmark = pytest.mark.e2e

_TRASH_BTN = "#navTrash"
_TRASH_PANEL = "#trashPanel"


def test_trash_panel_opens(page, live_server):
    page.goto(live_server)
    page.locator(_TRASH_BTN).click()
    page.locator(_TRASH_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(_TRASH_PANEL).is_visible()


def test_trash_panel_shows_aap_page_chrome(page, live_server):
    """Trash panel renders the AAP page chrome: icon tile + title + kicker."""
    page.goto(live_server)
    page.locator(_TRASH_BTN).click()
    page.locator(_TRASH_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(f"{_TRASH_PANEL} .aap-page__title").is_visible()
    assert page.locator(f"{_TRASH_PANEL} .aap-page__icon").is_visible()


def test_trash_panel_survives_reload(page, live_server):
    """Reloading ?view=trash stays on trash panel, not redirected to list/editor."""
    page.goto(f"{live_server}/?view=trash")
    page.locator(_TRASH_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(_TRASH_PANEL).is_visible()
    assert not page.locator("#seriesListPanel").is_visible()


def test_trash_empty_or_rows(page, live_server):
    """Trash panel renders either .aap-trash-row items or an empty-state paragraph."""
    page.goto(live_server)
    page.locator(_TRASH_BTN).click()
    page.locator(_TRASH_PANEL).wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(800)
    has_rows = page.locator(f"{_TRASH_PANEL} .aap-trash-row").count() > 0
    has_empty = page.locator(f"{_TRASH_PANEL} #trashContent p").count() > 0
    assert has_rows or has_empty


def test_trash_kicker_updates_after_load(page, live_server):
    """Trash kicker shows dynamic content (counts or auto-purge note) after data loads."""
    page.goto(live_server)
    page.locator(_TRASH_BTN).click()
    page.locator(_TRASH_PANEL).wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(800)
    kicker = page.locator(f"{_TRASH_PANEL} .aap-page__kicker")
    assert kicker.is_visible()
    text = kicker.inner_text()
    assert "auto-purged" in text
