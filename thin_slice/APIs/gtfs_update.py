#!/usr/bin/env python3
# """
# NTA GTFS-RT TripUpdates joiner (local static GTFS folder)

# Testing-friendly:
# - Uses an existing unzipped static GTFS folder on your PC (e.g. Downloads/gtfs/)
# - Does NOT download/update by default
# - If you enable ALLOW_DOWNLOAD_REFRESH=1, it can refresh when joins fail

# Install:
#   pip install requests gtfs-realtime-bindings

# Env vars:
#   NTA_API_KEY                     (required)
#   STATIC_GTFS_DIR                 (required) path to unzipped GTFS folder containing routes.txt, trips.txt
#   NTA_GTFSRT_TRIPUPDATES_URL      (optional) default: https://api.nationaltransport.ie/gtfsr/v2/TripUpdates
#   ALLOW_DOWNLOAD_REFRESH          (optional) 0/1 default: 0
#   NTA_GTFS_STATIC_URL             (optional) default: https://api.nationaltransport.ie/gtfs
#   REFRESH_COOLDOWN_SECONDS        (optional) default: 3600

# Example (mac/linux):
#   export NTA_API_KEY="..."
#   export STATIC_GTFS_DIR="$HOME/Downloads/GTFS"   # folder with routes.txt, trips.txt
#   python nta_local_gtfsrt_join.py

# Example (windows powershell):
#   setx NTA_API_KEY "..."
#   setx STATIC_GTFS_DIR "C:\Users\You\Downloads\GTFS"
# """

from __future__ import annotations

import csv
import io
import os
import shutil
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import requests

from google.transit import gtfs_realtime_pb2


# -----------------------------
# Config
# -----------------------------

API_KEY = "1fea1c21bef840e6bf0241e34a41e5d8"
if not API_KEY:
    raise SystemExit("ERROR: Set env var NTA_API_KEY")

STATIC_GTFS_DIR = "C:/Users/awals/Downloads/GTFS"
if not STATIC_GTFS_DIR:
    raise SystemExit("ERROR: Set env var STATIC_GTFS_DIR to your unzipped GTFS folder")

GTFS_DIR = Path(STATIC_GTFS_DIR).expanduser().resolve()
if not GTFS_DIR.exists():
    raise SystemExit(f"ERROR: STATIC_GTFS_DIR does not exist: {GTFS_DIR}")

TRIPUPDATES_URL = os.environ.get(
    "NTA_GTFSRT_TRIPUPDATES_URL",
    "https://api.nationaltransport.ie/gtfsr/v2/TripUpdates",
).strip()

ALLOW_DOWNLOAD_REFRESH = os.environ.get("ALLOW_DOWNLOAD_REFRESH", "0").strip() == "1"
STATIC_GTFS_URL = os.environ.get(
    "NTA_GTFS_STATIC_URL", "https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip"
).strip()
REFRESH_COOLDOWN_SECONDS = int(os.environ.get("REFRESH_COOLDOWN_SECONDS", "3600"))

STATE_FILE = GTFS_DIR / "_last_refresh_epoch.txt"


def headers() -> Dict[str, str]:
    return {"x-api-key": API_KEY}


def read_last_refresh_epoch() -> Optional[int]:
    try:
        return int(STATE_FILE.read_text().strip())
    except Exception:
        return None


def write_last_refresh_epoch(epoch: int) -> None:
    STATE_FILE.write_text(str(epoch))


def can_refresh_now() -> bool:
    last = read_last_refresh_epoch()
    if last is None:
        return True
    return (time.time() - last) >= REFRESH_COOLDOWN_SECONDS


# -----------------------------
# Static GTFS loading
# -----------------------------


@dataclass(frozen=True)
class RouteInfo:
    route_id: str
    agency_id: str
    route_short_name: str
    route_long_name: str

    @property
    def stable_key(self) -> str:
        # Your stable/business key (good for linking in your app)
        return f"{self.agency_id}:{self.route_short_name}".strip(":")


@dataclass
class StaticIndex:
    route_id_to_route: Dict[str, RouteInfo]
    trip_id_to_route_id: Dict[str, str]


def load_static_index(gtfs_dir: Path) -> StaticIndex:
    routes_path = gtfs_dir / "routes.txt"
    trips_path = gtfs_dir / "trips.txt"

    if not routes_path.exists():
        raise FileNotFoundError(f"Missing routes.txt in {gtfs_dir}")
    if not trips_path.exists():
        raise FileNotFoundError(f"Missing trips.txt in {gtfs_dir}")

    route_id_to_route: Dict[str, RouteInfo] = {}
    with routes_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            route_id = (r.get("route_id") or "").strip()
            if not route_id:
                continue
            route_id_to_route[route_id] = RouteInfo(
                route_id=route_id,
                agency_id=(r.get("agency_id") or "").strip(),
                route_short_name=(r.get("route_short_name") or "").strip(),
                route_long_name=(r.get("route_long_name") or "").strip(),
            )

    trip_id_to_route_id: Dict[str, str] = {}
    with trips_path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            trip_id = (r.get("trip_id") or "").strip()
            route_id = (r.get("route_id") or "").strip()
            if trip_id and route_id:
                trip_id_to_route_id[trip_id] = route_id

    print(f"[static] Loaded routes={len(route_id_to_route):,} trips={len(trip_id_to_route_id):,} from {gtfs_dir}")
    return StaticIndex(route_id_to_route=route_id_to_route, trip_id_to_route_id=trip_id_to_route_id)


# -----------------------------
# Optional: refresh static GTFS into your local folder
# -----------------------------


def refresh_static_gtfs_into_folder(target_dir: Path) -> None:
    """
    Downloads static GTFS zip and replaces files inside target_dir.

    WARNING: This will overwrite routes.txt/trips.txt/etc in your chosen folder.
    For testing, point STATIC_GTFS_DIR at a dedicated folder (not your real Downloads zip).
    """
    if not ALLOW_DOWNLOAD_REFRESH:
        print("[static] Refresh requested but ALLOW_DOWNLOAD_REFRESH=0; skipping download.")
        return

    if not can_refresh_now():
        print("[static] Refresh cooldown active; skipping download.")
        return

    tmp_dir = target_dir.parent / (target_dir.name + "_tmp_extract")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[static] Downloading static GTFS from {STATIC_GTFS_URL} -> {target_dir}")
    r = requests.get(STATIC_GTFS_URL, headers=headers(), timeout=60)
    r.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(tmp_dir)

    # Replace files inside target_dir (keep the folder path stable for your app)
    # Clear existing
    for child in target_dir.iterdir():
        if child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)

    # Move extracted contents into target_dir
    for child in tmp_dir.iterdir():
        shutil.move(str(child), str(target_dir / child.name))

    shutil.rmtree(tmp_dir)

    write_last_refresh_epoch(int(time.time()))
    (target_dir / "_last_refreshed_utc.txt").write_text(datetime.now(timezone.utc).isoformat())
    print(f"[static] Refreshed static GTFS into {target_dir}")


# -----------------------------
# GTFS-RT fetch + join
# -----------------------------


def fetch_tripupdates() -> gtfs_realtime_pb2.FeedMessage:
    r = requests.get(TRIPUPDATES_URL, headers=headers(), timeout=30)
    r.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)
    return feed


def resolve_route(index: StaticIndex, trip_id: str, route_id: str) -> Optional[RouteInfo]:
    # Prefer trip_id->route_id join (often more reliable), then fallback to realtime route_id
    if trip_id and trip_id in index.trip_id_to_route_id:
        rid = index.trip_id_to_route_id[trip_id]
        return index.route_id_to_route.get(rid)
    if route_id:
        return index.route_id_to_route.get(route_id)
    return None


def main() -> int:
    # Load static GTFS from your local folder
    index = load_static_index(GTFS_DIR)

    # Fetch realtime
    print(f"[rt] Fetching TripUpdates: {TRIPUPDATES_URL}")
    feed = fetch_tripupdates()
    print(f"[rt] Entities: {len(feed.entity):,}")

    misses = 0

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue

        trip = entity.trip_update.trip
        trip_id = trip.trip_id or ""
        route_id = trip.route_id or ""

        route = resolve_route(index, trip_id=trip_id, route_id=route_id)
        if route is None:
            misses += 1
            print(f"[miss] trip_id={trip_id!r} route_id={route_id!r}")

            # Optional: refresh local folder then retry once
            if ALLOW_DOWNLOAD_REFRESH:
                refresh_static_gtfs_into_folder(GTFS_DIR)
                index = load_static_index(GTFS_DIR)
                route = resolve_route(index, trip_id=trip_id, route_id=route_id)
    print(f"[done] misses={misses:,} (ALLOW_DOWNLOAD_REFRESH={int(ALLOW_DOWNLOAD_REFRESH)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
