"""
Backend bus-stops endpoint.

GET /buses/stops
  Returns Dublin bus stops near city centre from OpenStreetMap Overpass API.
"""

import time
from threading import Lock
import requests
from flask import Blueprint, jsonify, request

buses_bp = Blueprint("buses", __name__, url_prefix="/buses")

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603
_RADIUS_M = 5000
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
