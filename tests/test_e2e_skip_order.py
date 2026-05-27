"""Skipped images must render at the end of the library grid.

The DB sort_order must NOT be changed — only the visual display order changes.
"""

import pytest
import requests

pytestmark = pytest.mark.e2e


@pytest.fixture
def series_with_mixed_images(live_server):
    """Create series with 3 images: pending, skip, pending (in that DB order)."""
    sid = requests.post(f"{live_server}/api/series", json={"title": "Skip Order Test"}).json()["id"]

    img_a = requests.post(
        f"{live_server}/api/series/{sid}/images/register",
        json={"r2_key": "images/a.jpg", "original_filename": "a.jpg"},
    ).json()["id"]

    img_b = requests.post(
        f"{live_server}/api/series/{sid}/images/register",
        json={"r2_key": "images/b.jpg", "original_filename": "b.jpg"},
    ).json()["id"]

    img_c = requests.post(
        f"{live_server}/api/series/{sid}/images/register",
        json={"r2_key": "images/c.jpg", "original_filename": "c.jpg"},
    ).json()["id"]

    # Mark middle image as skip
    requests.patch(f"{live_server}/api/images/{img_b}/status", json={"status": "skip"})

    return {"series_id": sid, "img_a": img_a, "img_b": img_b, "img_c": img_c}


def test_skipped_image_renders_last_in_library_grid(page, live_server, series_with_mixed_images):
    """img_b (skip) is 2nd in DB order but must appear after img_a and img_c."""
    data = series_with_mixed_images
    page.goto(f"{live_server}/?series={data['series_id']}")

    # Wait for editor to load
    page.locator("#libraryGrid [data-image-id]").first.wait_for(timeout=10000)

    thumb_ids = page.locator("#libraryGrid [data-image-id]").evaluate_all(
        "els => els.map(e => e.dataset.imageId)"
    )

    assert data["img_b"] in thumb_ids, "skipped image should appear in libraryGrid"

    skip_index = thumb_ids.index(data["img_b"])
    non_skip_ids = [data["img_a"], data["img_c"]]
    for nid in non_skip_ids:
        if nid in thumb_ids:
            assert thumb_ids.index(nid) < skip_index, (
                f"non-skipped image {nid} (index {thumb_ids.index(nid)}) "
                f"should appear before skipped image {data['img_b']} (index {skip_index})"
            )


def test_skipped_images_all_render_last_when_multiple_skipped(page, live_server):
    """When multiple skipped images, all must come after all non-skipped."""
    sid = requests.post(f"{live_server}/api/series", json={"title": "Multi Skip Test"}).json()["id"]

    ids = []
    for name in ["x.jpg", "y.jpg", "z.jpg", "w.jpg"]:
        iid = requests.post(
            f"{live_server}/api/series/{sid}/images/register",
            json={"r2_key": f"images/{name}", "original_filename": name},
        ).json()["id"]
        ids.append(iid)

    # Skip 1st and 3rd images (indices 0 and 2)
    requests.patch(f"{live_server}/api/images/{ids[0]}/status", json={"status": "skip"})
    requests.patch(f"{live_server}/api/images/{ids[2]}/status", json={"status": "skip"})

    page.goto(f"{live_server}/?series={sid}")
    page.locator("#libraryGrid [data-image-id]").first.wait_for(timeout=10000)

    thumb_ids = page.locator("#libraryGrid [data-image-id]").evaluate_all(
        "els => els.map(e => e.dataset.imageId)"
    )

    skip_indices = [thumb_ids.index(ids[0]), thumb_ids.index(ids[2])]
    non_skip_indices = [thumb_ids.index(ids[1]), thumb_ids.index(ids[3])]

    assert max(non_skip_indices) < min(skip_indices), (
        f"all non-skipped indices {non_skip_indices} must precede "
        f"all skipped indices {skip_indices}"
    )
