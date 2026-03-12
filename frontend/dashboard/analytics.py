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

    buses = snapshot.get("buses") or {}
    top_served = buses.get("top_served_stops") or []
    if not top_served and buses.get("stop_frequencies") and buses.get("stops"):
        name_by_id = {s.get("stop_id"): s.get("name") for s in buses.get("stops", [])}
        ranked = sorted(buses["stop_frequencies"].items(), key=lambda x: x[1], reverse=True)[:10]
        top_served = [
            {"stop_id": stop_id, "name": name_by_id.get(stop_id, stop_id), "buses": count} for stop_id, count in ranked
        ]

    if top_served:
        bus_labels = [s.get("name", s.get("stop_id", "Stop")) for s in top_served]
        bus_values = [s.get("buses", 0) for s in top_served]
    else:
        bus_labels = ["No Data"]
        bus_values = [0]
    bus_chart = {"labels": bus_labels, "values": bus_values}

    wait_summary = buses.get("wait_time_summary") or []
    wait_counts = buses.get("wait_time_counts") or {}
    wait_chart = {
        "labels": [],
        "values": [],
        "colors": [],
        "meta": {
            "good": wait_counts.get("good", 0),
            "ok": wait_counts.get("ok", 0),
            "poor": wait_counts.get("poor", 0),
        },
    }

    best_waits = buses.get("wait_time_best") or []
    worst_waits = buses.get("wait_time_worst") or []
    if best_waits:
        best_labels = [s.get("name", s.get("stop_id", "Stop")) for s in best_waits]
        best_values = [s.get("avg_wait_min", 0) for s in best_waits]
    else:
        best_labels = ["No Data"]
        best_values = [0]
    if worst_waits:
        worst_labels = [s.get("name", s.get("stop_id", "Stop")) for s in worst_waits]
        worst_values = [s.get("avg_wait_min", 0) for s in worst_waits]
    else:
        worst_labels = ["No Data"]
        worst_values = [0]
    wait_best_chart = {"labels": best_labels, "values": best_values}
    wait_worst_chart = {"labels": worst_labels, "values": worst_values}

    importance = buses.get("top_importance_stops") or []
    if importance:
        imp_labels = [s.get("name", s.get("stop_id", "Stop")) for s in importance]
        imp_values = [s.get("score", 0) for s in importance]
    else:
        imp_labels = ["No Data"]
        imp_values = [0]
    importance_chart = {"labels": imp_labels, "values": imp_values}

    # Importance distribution (all stops)
    scores = list((buses.get("stop_importance_scores") or {}).values())
    if scores:
        bins = [i / 10 for i in range(0, 11)]  # 0.0 .. 1.0
        counts = [0] * 10
        for s in scores:
            idx = int(min(9, max(0, s * 10)))
            counts[idx] += 1
        dist_labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(10)]
        dist_values = counts

        # CDF (percentile curve)
        sorted_scores = sorted(scores)
        cdf_labels = [f"{i*10}%" for i in range(0, 11)]
        cdf_values = []
        n = len(sorted_scores)
        for p in range(0, 11):
            if n == 1:
                cdf_values.append(round(sorted_scores[0], 3))
            else:
                idx = int(round((p / 10) * (n - 1)))
                cdf_values.append(round(sorted_scores[idx], 3))
    else:
        dist_labels = ["No Data"]
        dist_values = [0]
        cdf_labels = ["No Data"]
        cdf_values = [0]

    importance_dist_chart = {"labels": dist_labels, "values": dist_values}
    importance_cdf_chart = {"labels": cdf_labels, "values": cdf_values}

    # Bus heatmap data (limit size for frontend performance)
    heat_points = []
    stops = buses.get("stops") or []
    freqs = buses.get("stop_frequencies") or {}
    for s in stops:
        sid = s.get("stop_id")
        if not sid:
            continue
        count = freqs.get(sid)
        if not count:
            continue
        heat_points.append(
            {
                "stop_id": sid,
                "name": s.get("name") or sid,
                "lat": s.get("lat"),
                "lon": s.get("longitude") or s.get("lon"),
                "count": count,
            }
        )
    heat_points.sort(key=lambda x: x["count"], reverse=True)
    heat_points = heat_points[:500]

    return {
        "air_quality_chart": air_quality_chart,
        "bike_chart": bike_chart,
        "traffic_chart": traffic_chart,
        "bus_chart": bus_chart,
        "bus_wait_chart": wait_chart,
        "bus_wait_best_chart": wait_best_chart,
        "bus_wait_worst_chart": wait_worst_chart,
        "bus_importance_chart": importance_chart,
        "bus_importance_dist_chart": importance_dist_chart,
        "bus_importance_cdf_chart": importance_cdf_chart,
        "bus_heatmap": heat_points,
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
