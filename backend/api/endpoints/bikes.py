import math
from flask import Blueprint, jsonify, request, current_app

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.bikes_adapter import BikesAdapter
from backend.adapters.bike_stations_adapter import BikeStationsAdapter
from backend.fallback.cache import AdapterCache
from backend.fallback.predictors import default_predictor
from backend.fallback.resolver import resolve_with_cache

bikes_bp = Blueprint("bikes", __name__)

_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603


def _get_adapter_cache() -> AdapterCache:
    cache = current_app.config.get("ADAPTER_CACHE")
    if cache is None:
        cache = AdapterCache()
        current_app.config["ADAPTER_CACHE"] = cache
    return cache


def _distance_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    r = 6371.0
    d_lat = math.radians(b_lat - a_lat)
    d_lon = math.radians(b_lon - a_lon)
    lat1 = math.radians(a_lat)
    lat2 = math.radians(b_lat)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _parse_radius_km(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        radius = float(raw)
    except ValueError:
        return None
    return max(0.1, min(radius, 50.0))


def _parse_coord(raw: str | None, default: float) -> float:
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@bikes_bp.get("/bikes")
def get_bikes():
    location = request.args.get("location", "dublin")

    cache = _get_adapter_cache()
    service = SnapshotService(
        adapter_specs=[AdapterCallSpec(adapter=BikesAdapter(), kwargs={})],
        cache=cache,
        predictor=default_predictor,
    )
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))


@bikes_bp.get("/bikes/stations")
def get_bike_stations():
    """Return per-station Dublin Bikes data for map display."""
    radius_km = _parse_radius_km(request.args.get("radius_km"))
    center_lat = _parse_coord(request.args.get("lat"), _DUBLIN_LAT)
    center_lon = _parse_coord(request.args.get("lon"), _DUBLIN_LON)

    cache = _get_adapter_cache()
    result = resolve_with_cache(
        BikeStationsAdapter(),
        cache,
        predictor=default_predictor,
    )
    if result.snapshot is None:
        return jsonify({"error": "Unable to load bike stations"}), 502

    stations = result.snapshot
    if radius_km is not None:
        filtered = []
        for station in stations:
            try:
                lat = float(station.get("lat"))
                lon = float(station.get("lon"))
            except (TypeError, ValueError):
                continue
            if _distance_km(center_lat, center_lon, lat, lon) <= radius_km:
                filtered.append(station)
        stations = filtered

    return jsonify(stations)
