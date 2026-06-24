"""Selecting an image must persist without clicking a Save button.

Reorder and skip already autosave instantly; selection (queued status) used to
require an explicit Save click and was easy to forget.
"""

import uuid

import pytest
import requests

pytestmark = pytest.mark.e2e


@pytest.fixture
def series_with_two_images(live_server):
    # Title must be unique per test: the app's pushState URL uses the series
    # title as a pretty slug, and reload re-resolves by title — a shared title
    # across tests would make reload land on a different test's series.
    title = f"Selection Persistence {uuid.uuid4().hex[:8]}"
    sid = requests.post(f"{live_server}/api/series", json={"title": title}).json()["id"]

    img_a = requests.post(
        f"{live_server}/api/series/{sid}/images/register",
        json={"r2_key": "images/a.jpg", "original_filename": "a.jpg"},
    ).json()["id"]

    img_b = requests.post(
        f"{live_server}/api/series/{sid}/images/register",
        json={"r2_key": "images/b.jpg", "original_filename": "b.jpg"},
    ).json()["id"]

    return {"series_id": sid, "img_a": img_a, "img_b": img_b}


def test_selecting_image_autosaves_without_save_click(page, live_server, series_with_two_images):
    data = series_with_two_images
    page.goto(f"{live_server}/?series={data['series_id']}")

    select_btn = page.locator(f'[data-select-btn="{data["img_a"]}"]')
    select_btn.wait_for(timeout=10000)
    select_btn.click()

    # Debounce window is ~600ms; give it room then check the server directly
    # without ever clicking a Save button.
    page.wait_for_timeout(1000)

    series = requests.get(f"{live_server}/api/series/{data['series_id']}").json()
    img_a = next(i for i in series["images"] if i["id"] == data["img_a"])
    assert img_a["status"] == "queued"


def test_selection_survives_reload_without_save_click(page, live_server, series_with_two_images):
    data = series_with_two_images
    page.goto(f"{live_server}/?series={data['series_id']}")

    select_btn = page.locator(f'[data-select-btn="{data["img_a"]}"]')
    select_btn.wait_for(timeout=10000)
    select_btn.click()
    page.wait_for_timeout(1000)

    page.reload()
    selected_thumb = page.locator(f'.aap-thumb.is-selected[data-image-id="{data["img_a"]}"]')
    selected_thumb.wait_for(timeout=10000)
    assert selected_thumb.count() == 1


def test_no_save_button_in_action_bar(page, live_server, series_with_two_images):
    data = series_with_two_images
    page.goto(f"{live_server}/?series={data['series_id']}")

    select_btn = page.locator(f'[data-select-btn="{data["img_a"]}"]')
    select_btn.wait_for(timeout=10000)
    select_btn.click()

    action_bar = page.locator("#imageActionBar")
    action_bar.wait_for(timeout=5000)
    assert action_bar.get_by_text("Save", exact=False).count() == 0
