"""
Desktop app support endpoint.

GET /desktop/cache-warmup
  Returns snapshot + bike stations + bus stops in a single call so the
  desktop app can warm its local SQLite cache on startup without making
  three separate round-trips.
"""

from __future__ import annotations

import requests
from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify

from backend.api.serializers import to_jsonable
from backend.fallback.cache import AdapterCache
from backend.services.snapshot_service import SnapshotService
from backend.api.endpoints.snapshot import build_adapter_specs

desktop_bp = Blueprint("desktop", __name__)

_CITYBIKES_URL = "https://api.citybik.es/v2/networks/dublinbikes"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603
_RADIUS_M = 5000
_RADIUS_KM = 5.0


def _get_adapter_cache() -> AdapterCache:
    cache = current_app.config.get("ADAPTER_CACHE")
    if cache is None:
        cache = AdapterCache()
        current_app.config["ADAPTER_CACHE"] = cache
    return cache


def _fetch_bike_stations() -> list:
    try:
        resp = requests.get(_CITYBIKES_URL, timeout=5)
        resp.raise_for_status()
        stations = resp.json()["network"]["stations"]
        return [
            {
                "name": s["name"],
                "lat": s["latitude"],
                "lon": s["longitude"],
                "free_bikes": s["free_bikes"],
                "empty_slots": s["empty_slots"],
                "total": s["extra"]["slots"],
            }
            for s in stations
        ]
    except Exception:
        return []


def _fetch_bus_stops() -> list:
    query = f"[out:json];" f'node["highway"="bus_stop"](around:{_RADIUS_M},{_DUBLIN_LAT},{_DUBLIN_LON});' f"out;"
    try:
        resp = requests.post(_OVERPASS_URL, data=query, timeout=20)
        resp.raise_for_status()
        stops = []
        for e in resp.json().get("elements", []):
            if "lat" not in e or "lon" not in e:
                continue
            tags = e.get("tags", {})
            stops.append(
                {
                    "name": tags.get("name") or tags.get("ref") or "Bus Stop",
                    "lat": e["lat"],
                    "lon": e["lon"],
                    "ref": tags.get("ref", ""),
                    "routes": tags.get("route_ref", ""),
                }
            )
        return stops
    except Exception:
        return []


@desktop_bp.get("/desktop/cache-warmup")
def cache_warmup():
    """Single-call cache seed for the desktop app.

    Returns the full snapshot, per-station bike data, and bus stops so the
    desktop client can populate its local SQLite cache in one HTTP request.
    All three fetches run sequentially; partial results are returned if any
    individual source fails.
    """
    adapter_specs = build_adapter_specs(
        include=["bikes", "traffic", "airquality", "tours"],
        radius_km=_RADIUS_KM,
        latitude=_DUBLIN_LAT,
        longitude=_DUBLIN_LON,
    )
    cache = _get_adapter_cache()
    service = SnapshotService(adapter_specs=adapter_specs, cache=cache)
    snapshot = service.build_snapshot(location="dublin")

    return jsonify(
        {
            "snapshot": to_jsonable(snapshot),
            "bike_stations": _fetch_bike_stations(),
            "bus_stops": _fetch_bus_stops(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    )
