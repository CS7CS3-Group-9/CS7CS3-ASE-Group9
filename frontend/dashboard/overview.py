import requests
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, jsonify, current_app

overview_bp = Blueprint("overview", __name__, url_prefix="/dashboard")


def _fetch_snapshot(backend_url):
    try:
        resp = requests.get(
            f"{backend_url}/snapshot",
            params=[
                ("location", "dublin"),
                ("radius_km", "5"),
                ("lat", "53.3498"),
                ("lon", "-6.2603"),
                ("include", "bikes"),
                ("include", "traffic"),
                ("include", "airquality"),
                ("include", "tours"),
            ],
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:
        return {}, str(e)


def _fetch_bus_stops(backend_url):
    """Fetch Dublin bus stops from the backend."""
    try:
        resp = requests.get(f"{backend_url}/buses/stops", timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _fetch_bike_stations(backend_url):
    """Fetch per-station Dublin Bikes data from the backend."""
    try:
        resp = requests.get(f"{backend_url}/bikes/stations", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _build_recommendations(bikes, traffic, airquality):
    recs = []

    if traffic:
        level = traffic.get("congestion_level", "low")
        if level == "high":
            recs.append({
                "title": "High Traffic Congestion",
                "description": "Significant traffic delays detected in Dublin city centre. Consider using public transport or alternative routes.",
                "priority": "High",
                "source": "traffic",
            })
        elif level == "medium":
            recs.append({
                "title": "Moderate Traffic Congestion",
                "description": "Some traffic congestion in the area. Allow extra travel time if driving.",
                "priority": "Medium",
                "source": "traffic",
            })
        total = traffic.get("total_incidents", 0)
        if total > 10:
            recs.append({
                "title": f"{total} Active Traffic Incidents",
                "description": "Multiple traffic incidents reported. Check live traffic updates before travelling.",
                "priority": "Medium",
                "source": "traffic",
            })

    if bikes:
        available = bikes.get("available_bikes", 0)
        if available < 10:
            recs.append({
                "title": "Low Bike Availability",
                "description": f"Only {available} bikes available city-wide. Consider alternative transport.",
                "priority": "High",
                "source": "bikes",
            })
        elif available > 100:
            recs.append({
                "title": "Good Bike Availability",
                "description": f"{available} bikes available across the city. Great conditions for cycling!",
                "priority": "Low",
                "source": "bikes",
            })

    if airquality:
        aqi = airquality.get("aqi_value")
        if aqi is not None:
            if aqi > 100:
                recs.append({
                    "title": "Poor Air Quality",
                    "description": f"Air Quality Index is {aqi}. Sensitive groups should avoid prolonged outdoor activity.",
                    "priority": "High",
                    "source": "air_quality",
                })
            elif aqi > 50:
                recs.append({
                    "title": "Moderate Air Quality",
                    "description": f"Air Quality Index is {aqi}. Generally acceptable but may cause issues for very sensitive people.",
                    "priority": "Medium",
                    "source": "air_quality",
                })

    if not recs:
        recs.append({
            "title": "All Clear",
            "description": "All city systems operating normally. No special advisories at this time.",
            "priority": "Low",
            "source": "system",
        })

    return recs


@overview_bp.get("")
@overview_bp.get("/")
def dashboard():
    backend_url = current_app.config["BACKEND_API_URL"]
    snapshot, error = _fetch_snapshot(backend_url)

    bikes = snapshot.get("bikes")
    traffic = snapshot.get("traffic")
    airquality = snapshot.get("airquality")
    tours = snapshot.get("tours")
    timestamp = snapshot.get("timestamp")
    source_status = snapshot.get("source_status", {})
    recommendations = _build_recommendations(bikes, traffic, airquality)

    return render_template(
        "dashboard/index.html",
        bikes=bikes,
        traffic=traffic,
        airquality=airquality,
        tours=tours,
        recommendations=recommendations,
        timestamp=timestamp,
        source_status=source_status,
        backend_error=error,
        refresh_interval=current_app.config["REFRESH_INTERVAL"],
    )


@overview_bp.get("/data")
def dashboard_data():
    backend_url = current_app.config["BACKEND_API_URL"]

    # Run all three slow fetches in parallel so the page loads faster
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_snapshot      = pool.submit(_fetch_snapshot, backend_url)
        f_bike_stations = pool.submit(_fetch_bike_stations, backend_url)
        f_bus_stops     = pool.submit(_fetch_bus_stops, backend_url)

        snapshot, error = f_snapshot.result()
        bike_stations   = f_bike_stations.result()
        bus_stops       = f_bus_stops.result()

    recommendations = _build_recommendations(
        snapshot.get("bikes"),
        snapshot.get("traffic"),
        snapshot.get("airquality"),
    )
    return jsonify({
        "timestamp":     snapshot.get("timestamp"),
        "source_status": snapshot.get("source_status", {}),
        "bikes":         snapshot.get("bikes"),
        "traffic":       snapshot.get("traffic"),
        "airquality":    snapshot.get("airquality"),
        "tours":         snapshot.get("tours"),
        "bike_stations": bike_stations,
        "bus_stops":     bus_stops,
        "recommendations": recommendations,
        "error":         error,
    })
