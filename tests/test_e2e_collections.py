import pytest

pytestmark = pytest.mark.e2e

_COLL_BTN = "#navCollections"
_COLL_PANEL = "#collectionsPanel"


def test_collections_panel_opens(page, live_server):
    page.goto(live_server)
    page.locator(_COLL_BTN).click()
    page.locator(_COLL_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(_COLL_PANEL).is_visible()


def test_collections_panel_shows_aap_page_chrome(page, live_server):
    """Collections panel renders the AAP page chrome: icon tile + title + kicker."""
    page.goto(live_server)
    page.locator(_COLL_BTN).click()
    page.locator(_COLL_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(f"{_COLL_PANEL} .aap-page__title").is_visible()
    assert page.locator(f"{_COLL_PANEL} .aap-page__icon").is_visible()


def test_collections_panel_survives_reload(page, live_server):
    """Reloading ?view=collections stays on collections panel, not redirected to list/editor."""
    page.goto(f"{live_server}/?view=collections")
    page.locator(_COLL_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(_COLL_PANEL).is_visible()
    assert not page.locator("#seriesListPanel").is_visible()


def test_collections_shows_create_row(page, live_server):
    """Collections panel renders the create-row form with two inputs."""
    page.goto(live_server)
    page.locator(_COLL_BTN).click()
    page.locator(_COLL_PANEL).wait_for(state="visible", timeout=5000)
    assert page.locator(f"{_COLL_PANEL} .aap-create-row").is_visible()
    assert page.locator(f"{_COLL_PANEL} .aap-create-row input").count() >= 2


def test_collections_empty_or_rows(page, live_server):
    """Collections panel renders either .aap-collection-row items or an empty-state paragraph."""
    page.goto(live_server)
    page.locator(_COLL_BTN).click()
    page.locator(_COLL_PANEL).wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(800)
    has_rows = page.locator(f"{_COLL_PANEL} .aap-collection-row").count() > 0
    has_empty = page.locator(f"{_COLL_PANEL} #collectionsContent p").count() > 0
    assert has_rows or has_empty
