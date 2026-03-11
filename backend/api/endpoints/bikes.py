import time
from threading import Lock
import math
import requests
from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.bikes_adapter import BikesAdapter

bikes_bp = Blueprint("bikes", __name__)

_CITYBIKES_URL = "https://api.citybik.es/v2/networks/dublinbikes"
_CACHE_TTL_SECONDS = 60.0
_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603
_STATIONS_CACHE = {}
_STATIONS_LOCK = Lock()


def _cache_key(radius_km, lat, lon):
    return f"{radius_km or 'all'}:{lat:.4f}:{lon:.4f}"


def _get_cached_stations(cache_key):
    with _STATIONS_LOCK:
        entry = _STATIONS_CACHE.get(cache_key)
        if entry is None:
            return None
        age = time.time() - entry["timestamp"]
        if age <= _CACHE_TTL_SECONDS:
            return entry["data"]
    return None


def _distance_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    d_lat = math.radians(b_lat - a_lat)
    d_lon = math.radians(b_lon - a_lon)
    lat1 = math.radians(a_lat)
    lat2 = math.radians(b_lat)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


@bikes_bp.get("/bikes")
def get_bikes():
    location = request.args.get("location", "dublin")

    service = SnapshotService(
        adapter_specs=[
            AdapterCallSpec(
                adapter=BikesAdapter(),
                kwargs={},
                cache_ttl_seconds=_CACHE_TTL_SECONDS,
            )
        ]
    )
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))


@bikes_bp.get("/bikes/stations")
def get_bike_stations():
    """Return per-station Dublin Bikes data for map display."""
    radius_km = request.args.get("radius_km")
    center_lat = request.args.get("lat")
    center_lon = request.args.get("lon")
    try:
        radius_km = float(radius_km) if radius_km is not None else None
    except ValueError:
        radius_km = None
    if radius_km is not None:
        radius_km = max(0.1, min(radius_km, 50.0))
    try:
        center_lat = float(center_lat) if center_lat is not None else _DUBLIN_LAT
        center_lon = float(center_lon) if center_lon is not None else _DUBLIN_LON
    except ValueError:
        center_lat = _DUBLIN_LAT
        center_lon = _DUBLIN_LON

    cache_key = _cache_key(radius_km, center_lat, center_lon)
    cached = _get_cached_stations(cache_key)
    if cached is not None:
        resp = jsonify(cached)
        resp.headers["Cache-Control"] = f"public, max-age={int(_CACHE_TTL_SECONDS)}"
        return resp

    try:
        resp = requests.get(_CITYBIKES_URL, timeout=5)
        resp.raise_for_status()
        stations = resp.json()["network"]["stations"]
        payload = [
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
        if radius_km is not None:
            payload = [p for p in payload if _distance_km(center_lat, center_lon, p["lat"], p["lon"]) <= radius_km]
        with _STATIONS_LOCK:
            _STATIONS_CACHE[cache_key] = {
                "data": payload,
                "timestamp": time.time(),
            }
        response = jsonify(payload)
        response.headers["Cache-Control"] = f"public, max-age={int(_CACHE_TTL_SECONDS)}"
        return response
    except Exception as e:
        with _STATIONS_LOCK:
            cached = _STATIONS_CACHE.get(cache_key, {}).get("data")
        if cached is not None:
            resp = jsonify(cached)
            resp.headers["Cache-Control"] = "public, max-age=30"
            resp.headers["X-Cache"] = "stale"
            return resp
        return jsonify({"error": str(e)}), 502
