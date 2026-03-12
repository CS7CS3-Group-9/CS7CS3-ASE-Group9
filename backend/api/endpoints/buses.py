"""
Backend bus-stops endpoint.

GET /buses/stops
  Returns Dublin bus stops, enriched with arrivals in the next hour when GTFS is available.
"""

import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, jsonify

from backend.adapters.bus_adapter import BusAdapter

buses_bp = Blueprint("buses", __name__, url_prefix="/buses")

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603
_RADIUS_M = 5000
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GTFS_ROOT = _REPO_ROOT / "data" / "historical"
_GTFS_STOPS_CACHE = None
_GTFS_STOP_IDS_CACHE = None
_ARRIVALS_CACHE = {}
_ARRIVALS_CACHE_TS = None


def _load_gtfs_stops():
    global _GTFS_STOPS_CACHE, _GTFS_STOP_IDS_CACHE
    if _GTFS_STOPS_CACHE is not None and _GTFS_STOP_IDS_CACHE is not None:
        return _GTFS_STOPS_CACHE, _GTFS_STOP_IDS_CACHE

    stops_file = _GTFS_ROOT / "GTFS" / "stops.txt"
    adapter = BusAdapter(gtfs_path=_GTFS_ROOT)
    stops = []
    stop_ids = set()
    if not stops_file.exists():
        _GTFS_STOPS_CACHE = []
        _GTFS_STOP_IDS_CACHE = set()
        return _GTFS_STOPS_CACHE, _GTFS_STOP_IDS_CACHE

    with stops_file.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                lat = float(row["stop_lat"])
                lon = float(row["stop_lon"])
            except (KeyError, ValueError):
                continue
            if not adapter._is_within_dublin_bbox(lat, lon):
                continue
            stop_id = row.get("stop_id")
            if not stop_id:
                continue
            stop_ids.add(stop_id)
            stops.append(
                {
                    "stop_id": stop_id,
                    "name": row.get("stop_name") or "Bus Stop",
                    "lat": lat,
                    "lon": lon,
                    "ref": stop_id,
                    "routes": "",
                }
            )

    _GTFS_STOPS_CACHE = stops
    _GTFS_STOP_IDS_CACHE = stop_ids
    return _GTFS_STOPS_CACHE, _GTFS_STOP_IDS_CACHE


def _get_arrivals_next_hour(stop_ids):
    global _ARRIVALS_CACHE, _ARRIVALS_CACHE_TS
    try:
        now_local = datetime.now(ZoneInfo("Europe/Dublin"))
    except Exception:
        now_local = datetime.now(timezone.utc)

    if _ARRIVALS_CACHE_TS is not None:
        age_seconds = (now_local - _ARRIVALS_CACHE_TS).total_seconds()
        if age_seconds < 60:
            return _ARRIVALS_CACHE

    adapter = BusAdapter(gtfs_path=_GTFS_ROOT)
    _ARRIVALS_CACHE = adapter._count_arrivals_within_hour(stop_ids, now_local=now_local)
    _ARRIVALS_CACHE_TS = now_local
    return _ARRIVALS_CACHE


@buses_bp.get("/stops")
def bus_stops():
    """Return bus stops near Dublin city centre."""
    gtfs_stops = _GTFS_ROOT / "GTFS" / "stops.txt"
    if gtfs_stops.exists():
        try:
            stops, stop_ids = _load_gtfs_stops()
            arrivals = _get_arrivals_next_hour(stop_ids)
            enriched = []
            for stop in stops:
                item = dict(stop)
                item["arrivals_next_hour"] = arrivals.get(stop.get("stop_id"), 0)
                enriched.append(item)
            return jsonify(enriched)
        except Exception as e:
            return jsonify({"error": str(e)}), 502

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
        return jsonify(stops)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
