from flask import Blueprint, jsonify, request, current_app

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.bikes_adapter import BikesAdapter
from backend.adapters.bike_stations_adapter import BikeStationsAdapter
from backend.fallback.cache import AdapterCache
from backend.fallback.predictors import default_predictor
from backend.fallback.resolver import resolve_with_cache

bikes_bp = Blueprint("bikes", __name__)


def _get_adapter_cache() -> AdapterCache:
    cache = current_app.config.get("ADAPTER_CACHE")
    if cache is None:
        cache = AdapterCache()
        current_app.config["ADAPTER_CACHE"] = cache
    return cache


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
    cache = _get_adapter_cache()
    result = resolve_with_cache(
        BikeStationsAdapter(),
        cache,
        predictor=default_predictor,
    )
    if result.snapshot is None:
        return jsonify({"error": "Unable to load bike stations"}), 502
    return jsonify(result.snapshot)
