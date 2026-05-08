#!/usr/bin/env python3
"""
Bulk import series folders from local disk to AI Art Publisher.

Usage:
  python scripts/import_local.py --source /path/to/folders --app-url https://app.fly.dev

Reads .env.import from project root for R2 credentials.
"""

import argparse
import concurrent.futures
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
import httpx
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(".env")

_TS_RE = re.compile(r"^(\d{10,13})")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_created_at(filename: str) -> datetime | None:
    m = _TS_RE.match(filename)
    if not m:
        return None
    ts = int(m.group(1))
    if ts > 10**12:
        ts //= 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def find_image_files(folder: Path) -> list[Path]:
    return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in _IMAGE_EXTS)


def _upload_one(args):
    s3_client, bucket, filepath, r2_key = args
    s3_client.upload_file(str(filepath), bucket, r2_key)
    return r2_key


def import_series(
    source_dir: str,
    app_url: str,
    r2_endpoint: str,
    r2_access_key: str,
    r2_secret_key: str,
    r2_bucket: str,
    workers: int = 8,
):
    s3 = boto3.client(
        "s3",
        endpoint_url=r2_endpoint,
        aws_access_key_id=r2_access_key,
        aws_secret_access_key=r2_secret_key,
        region_name="auto",
    )

    folders = sorted(d for d in Path(source_dir).iterdir() if d.is_dir())
    print(f"Found {len(folders)} folders in {source_dir}")

    with httpx.Client(base_url=app_url, timeout=30) as api:
        # Collect already-imported folder names
        existing = set()
        page = 1
        while True:
            resp = api.get(
                "/api/series",
                params={
                    "status": "new,draft,approved,scheduled,posted,skip",
                    "limit": 100,
                    "page": page,
                },
            )
            data = resp.json()
            for s in data["items"]:
                if s["original_folder_name"]:
                    existing.add(s["original_folder_name"])
            if page * 100 >= data["total"]:
                break
            page += 1
        print(f"{len(existing)} series already imported, skipping")

        for folder in tqdm(folders, desc="Importing series"):
            if folder.name in existing:
                continue
            images = find_image_files(folder)
            if not images:
                continue

            timestamps = [parse_created_at(img.name) for img in images]
            timestamps = [t for t in timestamps if t]
            created_at = min(timestamps).isoformat() if timestamps else None

            resp = api.post(
                "/api/series",
                json={
                    "original_folder_name": folder.name,
                    "status": "new",
                    "created_at": created_at,
                },
            )
            resp.raise_for_status()
            series_id = resp.json()["id"]

            upload_tasks = []
            for img_path in images:
                ext = img_path.suffix.lower() or ".jpg"
                r2_key = f"images/{uuid.uuid4()}{ext}"
                upload_tasks.append((s3, r2_bucket, img_path, r2_key))

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                r2_keys = list(
                    tqdm(
                        pool.map(_upload_one, upload_tasks),
                        total=len(upload_tasks),
                        desc=f"  {folder.name[:30]}",
                        leave=False,
                    )
                )

            for img_path, r2_key in zip(images, r2_keys):
                created = parse_created_at(img_path.name)
                api.post(
                    f"/api/series/{series_id}/images/register",
                    json={
                        "r2_key": r2_key,
                        "original_filename": img_path.name,
                        "original_created_at": created.isoformat() if created else None,
                    },
                )

    print("Import complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk import series to AI Art Publisher")
    parser.add_argument(
        "--source", required=True, help="Path to folder containing series subfolders"
    )
    parser.add_argument(
        "--app-url", required=True, help="Deployed app URL, e.g. https://app.fly.dev"
    )
    parser.add_argument("--workers", type=int, default=8, help="Parallel upload threads")
    args = parser.parse_args()

    import_series(
        source_dir=args.source,
        app_url=args.app_url,
        r2_endpoint=os.environ["R2_ENDPOINT"],
        r2_access_key=os.environ["R2_ACCESS_KEY"],
        r2_secret_key=os.environ["R2_SECRET_KEY"],
        r2_bucket=os.environ["R2_BUCKET"],
        workers=args.workers,
    )
