from flask import Blueprint, render_template, current_app
from .overview import (
    _fetch_snapshot,
    _build_recommendations,
    _fetch_bike_stations,
    _fetch_bus_stops,
    _filter_points_within_radius,
    _SNAPSHOT_CACHE,
    _BUS_STOP_CACHE,
    _BIKE_STATION_CACHE,
    _NEEDS_CACHE,
)

recommendations_bp = Blueprint("recommendations", __name__, url_prefix="/dashboard/recommendations")


@recommendations_bp.get("")
@recommendations_bp.get("/")
def recommendations():
    if current_app.config.get("TESTING"):
        _SNAPSHOT_CACHE.clear()
        _BUS_STOP_CACHE.clear()
        _BIKE_STATION_CACHE.clear()
        _NEEDS_CACHE.clear()
    backend_url = current_app.config["BACKEND_API_URL"]
    radius_km = current_app.config.get("RADIUS_KM", 5)
    snapshot, error = _fetch_snapshot(backend_url, radius_km)
    bike_stations = _filter_points_within_radius(_fetch_bike_stations(backend_url, radius_km), radius_km)
    bus_stops = _filter_points_within_radius(_fetch_bus_stops(backend_url, radius_km), radius_km)
    recs = _build_recommendations(
        snapshot.get("bikes"),
        snapshot.get("traffic"),
        snapshot.get("airquality"),
        bike_stations=bike_stations,
        bus_stops=bus_stops,
        radius_km=radius_km,
    )
    return render_template(
        "dashboard/recommendations.html",
        recommendations=recs,
        timestamp=snapshot.get("timestamp"),
        backend_error=error,
    )
