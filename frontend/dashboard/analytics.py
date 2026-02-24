import requests
from flask import Blueprint, render_template, jsonify, current_app
from .overview import _fetch_snapshot

analytics_bp = Blueprint("analytics", __name__, url_prefix="/dashboard/analytics")


def _build_chart_data(snapshot):
    aq = snapshot.get("airquality") or {}
    pollutants = aq.get("pollutants") or {}
    aq_keys = ["pm2_5", "pm10", "nitrogen_dioxide", "carbon_monoxide", "ozone", "sulphur_dioxide"]
    aq_labels = ["PM2.5", "PM10", "NO\u2082", "CO", "O\u2083", "SO\u2082"]
    aq_values = [round(pollutants.get(k) or 0, 2) for k in aq_keys]
    air_quality_chart = {"labels": aq_labels, "values": aq_values}

    bikes = snapshot.get("bikes") or {}
    bike_labels = ["Available Bikes", "Empty Docks", "Stations Reporting"]
    bike_values = [
        bikes.get("available_bikes", 0),
        bikes.get("available_docks", 0),
        bikes.get("stations_reporting", 0),
    ]
    bike_chart = {"labels": bike_labels, "values": bike_values}

    traffic = snapshot.get("traffic") or {}
    by_category = traffic.get("incidents_by_category") or {}
    if by_category:
        traffic_labels = list(by_category.keys())
        traffic_values = list(by_category.values())
    else:
        traffic_labels = ["No Incidents"]
        traffic_values = [0]
    traffic_chart = {"labels": traffic_labels, "values": traffic_values}

    return {
        "air_quality_chart": air_quality_chart,
        "bike_chart": bike_chart,
        "traffic_chart": traffic_chart,
    }


@analytics_bp.get("")
@analytics_bp.get("/")
def analytics():
    backend_url = current_app.config["BACKEND_API_URL"]
    radius_km = current_app.config.get("RADIUS_KM", 5)
    snapshot, error = _fetch_snapshot(backend_url, radius_km)
    chart_data = _build_chart_data(snapshot)
    return render_template(
        "dashboard/analytics.html",
        chart_data=chart_data,
        timestamp=snapshot.get("timestamp"),
        backend_error=error,
    )


@analytics_bp.get("/data")
def analytics_data():
    backend_url = current_app.config["BACKEND_API_URL"]
    radius_km = current_app.config.get("RADIUS_KM", 5)
    snapshot, error = _fetch_snapshot(backend_url, radius_km)
    chart_data = _build_chart_data(snapshot)
    chart_data["timestamp"] = snapshot.get("timestamp")
    chart_data["error"] = error
    return jsonify(chart_data)
