"""E2E: loadSeriesDetail with silent=true must not show spinner.

Bug: poller calls loadSeriesDetail which inserts a spinner before fetching.
Spinner collapses the panel → page height shrinks → browser clamps scrollY
→ page jumps to top when content restores.

Fix: loadSeriesDetail({ silent: true }) skips the spinner.
"""

import pytest
import requests

pytestmark = pytest.mark.e2e


@pytest.fixture
def loaded_series(live_server, page):
    """Series with images, editor already loaded in the browser."""
    sid = requests.post(
        f"{live_server}/api/series", json={"title": "Scroll Preservation Test"}
    ).json()["id"]
    for i in range(4):
        requests.post(
            f"{live_server}/api/series/{sid}/images/register",
            json={"r2_key": f"images/p{i}.jpg", "original_filename": f"p{i}.jpg"},
        )
    page.goto(f"{live_server}/?series={sid}")
    page.locator("#libraryGrid [data-image-id]").first.wait_for(timeout=10000)
    return sid


def test_silent_load_does_not_show_spinner(page, live_server, loaded_series):
    """loadSeriesDetail(id, { silent: true }) must not flash the spinner."""
    spinner_appeared = page.evaluate(
        """async (sid) => {
            let spinnerSeen = false;
            const panel = document.getElementById('editorPanel');
            const observer = new MutationObserver(() => {
                if (panel.querySelector('.spinner-border')) spinnerSeen = true;
            });
            observer.observe(panel, { childList: true, subtree: true });
            await loadSeriesDetail(sid, { silent: true });
            observer.disconnect();
            return spinnerSeen;
        }""",
        loaded_series,
    )
    assert not spinner_appeared, (
        "loadSeriesDetail with silent=true must not insert a spinner — "
        "spinner collapses panel height and causes scroll jump"
    )


def test_silent_load_re_renders_editor(page, live_server, loaded_series):
    """silent load must still render the editor content after fetching."""
    page.evaluate(
        "async (sid) => { await loadSeriesDetail(sid, { silent: true }); }",
        loaded_series,
    )
    # editor topbar is always rendered by renderEditor
    page.locator("#editorPanel .aap-editor-topbar").wait_for(timeout=5000)
    assert page.locator("#editorPanel .aap-editor-topbar").is_visible()


def test_non_silent_load_shows_spinner(page, live_server, loaded_series):
    """Sanity: non-silent loadSeriesDetail must show the spinner (baseline)."""
    spinner_appeared = page.evaluate(
        """async (sid) => {
            let spinnerSeen = false;
            const panel = document.getElementById('editorPanel');
            const observer = new MutationObserver(() => {
                if (panel.querySelector('.spinner-border')) spinnerSeen = true;
            });
            observer.observe(panel, { childList: true, subtree: true });
            const call = loadSeriesDetail(sid);
            await call;
            observer.disconnect();
            return spinnerSeen;
        }""",
        loaded_series,
    )
    assert spinner_appeared, "Non-silent loadSeriesDetail should show spinner during fetch"
