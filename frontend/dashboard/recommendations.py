from flask import Blueprint, render_template, jsonify, current_app
from .overview import (
    _fetch_snapshot,
    _build_recommendations,
    _fetch_bike_stations,
    _fetch_bus_stops,
    _filter_points_within_radius,
    _parse_radius_km,
    _SNAPSHOT_CACHE,
    _BUS_STOP_CACHE,
    _BIKE_STATION_CACHE,
    _NEEDS_CACHE,
)
from concurrent.futures import ThreadPoolExecutor
from flask import request

recommendations_bp = Blueprint("recommendations", __name__, url_prefix="/dashboard/recommendations")


@recommendations_bp.get("")
@recommendations_bp.get("/")
def recommendations():
    backend_url = current_app.config["BACKEND_API_URL"]
    radius_km = _parse_radius_km(request.args.get("radius_km"))
    error = None

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_snapshot = pool.submit(_fetch_snapshot, backend_url, radius_km)
        f_bike_stations = pool.submit(_fetch_bike_stations, backend_url, radius_km)
        f_bus_stops = pool.submit(_fetch_bus_stops, backend_url, radius_km)

        snapshot, error = f_snapshot.result()
        bike_stations = f_bike_stations.result()
        bus_stops = f_bus_stops.result()

    bike_stations = _filter_points_within_radius(bike_stations, radius_km)
    bus_stops = _filter_points_within_radius(bus_stops, radius_km)
    recs = _build_recommendations(
        snapshot.get("bikes"),
        snapshot.get("traffic"),
        snapshot.get("airquality"),
        bike_stations=bike_stations,
        bus_stops=bus_stops,
        buses=snapshot.get("buses"),
        radius_km=radius_km,
    )

    return render_template(
        "dashboard/recommendations.html",
        recommendations=recs,
        timestamp=snapshot.get("timestamp"),
        backend_error=error,
    )


@recommendations_bp.get("/data")
def recommendations_data():
    if current_app.config.get("TESTING"):
        _SNAPSHOT_CACHE.clear()
        _BUS_STOP_CACHE.clear()
        _BIKE_STATION_CACHE.clear()
        _NEEDS_CACHE.clear()
    backend_url = current_app.config["BACKEND_API_URL"]
    radius_km = _parse_radius_km(request.args.get("radius_km") or current_app.config.get("RADIUS_KM", 5))

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_snapshot = pool.submit(_fetch_snapshot, backend_url, radius_km)
        f_bike_stations = pool.submit(_fetch_bike_stations, backend_url, radius_km)
        f_bus_stops = pool.submit(_fetch_bus_stops, backend_url, radius_km)

        snapshot, error = f_snapshot.result()
        bike_stations = f_bike_stations.result()
        bus_stops = f_bus_stops.result()

    bike_stations = _filter_points_within_radius(bike_stations, radius_km)
    bus_stops = _filter_points_within_radius(bus_stops, radius_km)
    recs = _build_recommendations(
        snapshot.get("bikes"),
        snapshot.get("traffic"),
        snapshot.get("airquality"),
        bike_stations=bike_stations,
        bus_stops=bus_stops,
        buses=snapshot.get("buses"),
        radius_km=radius_km,
    )
    return jsonify(
        {
            "recommendations": recs,
            "timestamp": snapshot.get("timestamp"),
            "error": error,
        }
    )
