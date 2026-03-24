"""
Backend bus-stops endpoint.

GET /buses/stops
  Returns Dublin bus stops, enriched with arrivals in the next hour when GTFS is available.
"""

import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, jsonify, request

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

_CACHE_TTL_SECONDS = 600.0
_STOPS_CACHE = {}
_STOPS_LOCK = Lock()


def _cache_key(radius_km, lat, lon):
    return f"{radius_km or 'all'}:{lat:.4f}:{lon:.4f}"


def _get_cached_stops(cache_key):
    with _STOPS_LOCK:
        entry = _STOPS_CACHE.get(cache_key)
        if entry is None:
            return None
        age = time.time() - entry["timestamp"]
        if age <= _CACHE_TTL_SECONDS:
            return entry["data"]
    return None


def _load_gtfs_stops():
    global _GTFS_STOPS_CACHE, _GTFS_STOP_IDS_CACHE
    if _GTFS_STOPS_CACHE is not None and _GTFS_STOP_IDS_CACHE is not None:
        return _GTFS_STOPS_CACHE, _GTFS_STOP_IDS_CACHE

    adapter = BusAdapter(gtfs_path=_GTFS_ROOT)
    stops_file = adapter._resolve_stops_file()
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
    stops_file = adapter._resolve_stops_file()
    stop_times_file = adapter._resolve_stop_times_file()

    # Prefer precomputed metrics if available to avoid scanning stop_times.txt.
    precomputed = adapter._load_precomputed_metrics(stops_file, stop_times_file)
    if precomputed is not None and precomputed.buses is not None:
        _ARRIVALS_CACHE = precomputed.buses.stop_arrivals_next_hour or {}
        _ARRIVALS_CACHE_TS = now_local
        return _ARRIVALS_CACHE

    _ARRIVALS_CACHE = adapter._count_arrivals_within_hour(stop_ids, now_local=now_local)
    _ARRIVALS_CACHE_TS = now_local
    return _ARRIVALS_CACHE


@buses_bp.get("/stops")
def bus_stops():
    """Return bus stops near Dublin city centre."""
    radius_km = None
    radius_raw = request.args.get("radius_km")
    if radius_raw is not None:
        try:
            radius_km = float(radius_raw)
        except ValueError:
            radius_km = None
    if radius_km is not None:
        radius_km = max(0.1, min(radius_km, 50.0))
    center_lat = request.args.get("lat")
    center_lon = request.args.get("lon")
    try:
        center_lat = float(center_lat) if center_lat is not None else _DUBLIN_LAT
        center_lon = float(center_lon) if center_lon is not None else _DUBLIN_LON
    except ValueError:
        center_lat = _DUBLIN_LAT
        center_lon = _DUBLIN_LON

    adapter = BusAdapter(gtfs_path=_GTFS_ROOT)
    gtfs_stops = adapter._resolve_stops_file()
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

    cache_key = _cache_key(radius_km, center_lat, center_lon)
    cached = _get_cached_stops(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        resp.headers["Cache-Control"] = f"public, max-age={int(_CACHE_TTL_SECONDS)}"
        return resp

    radius_m = int((radius_km or (_RADIUS_M / 1000.0)) * 1000)
    query = f"[out:json];" f'node["highway"="bus_stop"](around:{radius_m},{center_lat},{center_lon});' f"out;"
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
        with _STOPS_LOCK:
            _STOPS_CACHE[cache_key] = {
                "data": stops,
                "timestamp": time.time(),
            }
        response = jsonify(stops)
        response.headers["Cache-Control"] = f"public, max-age={int(_CACHE_TTL_SECONDS)}"
        return response
    except Exception as e:
        with _STOPS_LOCK:
            cached = _STOPS_CACHE.get(cache_key, {}).get("data")
        if cached is not None:
            resp = jsonify(cached)
            resp.headers["Cache-Control"] = "public, max-age=60"
            resp.headers["X-Cache"] = "stale"
            return resp
        return jsonify({"error": str(e)}), 502
