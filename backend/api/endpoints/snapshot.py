from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request, current_app

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService

from backend.adapters.bikes_adapter import BikesAdapter
from backend.adapters.traffic_adapter import TrafficAdapter
from backend.adapters.airquality_adapter import AirQualityAdapter
from backend.adapters.tour_adapter import TourAdapter
from backend.adapters.airquality_location_adapter import AirQualityLocationAdapter
from backend.adapters.bus_adapter import BusAdapter
from backend.fallback.cache import AdapterCache
from backend.fallback.predictors import default_predictor

snapshot_bp = Blueprint("snapshot", __name__)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GTFS_ROOT = _REPO_ROOT / "data" / "historical"

_CACHE_TTLS = {
    "bikes": 60.0,
    "traffic": 120.0,
    "airquality": 300.0,
    "tours": 600.0,
    "buses": 600.0,
}


def _get_adapter_cache() -> AdapterCache:
    cache = current_app.config.get("ADAPTER_CACHE")
    if cache is None:
        cache = AdapterCache()
        current_app.config["ADAPTER_CACHE"] = cache
    return cache


def build_adapter_specs(
    include: list[str],
    radius_km: float,
    latitude: float | None,
    longitude: float | None,
) -> list[AdapterCallSpec]:
    specs: list[AdapterCallSpec] = []

    if "bikes" in include:
        specs.append(
            AdapterCallSpec(
                adapter=BikesAdapter(),
                kwargs={},
                cache_ttl_seconds=_CACHE_TTLS["bikes"],
            )
        )

    if "traffic" in include:
        specs.append(
            AdapterCallSpec(
                adapter=TrafficAdapter(),
                kwargs={"radius_km": radius_km},
                cache_ttl_seconds=_CACHE_TTLS["traffic"],
            )
        )

    if "airquality" in include:
        specs.append(
            AdapterCallSpec(
                adapter=AirQualityLocationAdapter(),
                kwargs={"latitude": latitude, "longitude": longitude},
                cache_ttl_seconds=_CACHE_TTLS["airquality"],
            )
        )

    if "tours" in include:
        specs.append(
            AdapterCallSpec(
                adapter=TourAdapter(),
                kwargs={"radius_km": radius_km},
                cache_ttl_seconds=_CACHE_TTLS["tours"],
            )
        )

    if "buses" in include:
        specs.append(
            AdapterCallSpec(
                adapter=BusAdapter(gtfs_path=_GTFS_ROOT),
                kwargs={},
                cache_ttl_seconds=_CACHE_TTLS["buses"],
            )
        )

    return specs


@snapshot_bp.get("/snapshot")
def get_snapshot():
    location = request.args.get("location", "dublin")

    try:
        radius_km = float(request.args.get("radius_km", "1.0"))
    except ValueError:
        radius_km = 1.0
    radius_km = max(0.1, min(radius_km, 50.0))

    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon")
    latitude = None
    longitude = None
    try:
        if lat_raw is not None and lon_raw is not None:
            latitude = float(lat_raw)
            longitude = float(lon_raw)
    except ValueError:
        latitude = None
        longitude = None

    include = request.args.getlist("include")
    if not include:
        include = ["bikes", "traffic", "airquality", "tours", "buses"]

    adapter_specs = build_adapter_specs(include, radius_km, latitude, longitude)
    # Always attempt a live fetch for the real-time endpoint. Setting TTL to 0
    # bypasses the cache short-circuit in resolve_with_cache so the dashboard
    # never shows stale "cached" data. The AdapterCache is still populated on
    # success and used as a fallback if the live call fails.
    for spec in adapter_specs:
        spec.cache_ttl_seconds = 0
    cache = _get_adapter_cache()
    service = SnapshotService(adapter_specs=adapter_specs, cache=cache, predictor=default_predictor)
    snapshot = service.build_snapshot(location=location)

    return jsonify(to_jsonable(snapshot))
