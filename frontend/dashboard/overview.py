import math
import requests
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, jsonify, current_app, request

overview_bp = Blueprint("overview", __name__, url_prefix="/dashboard")

_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603
_BUS_STOP_CACHE = []


def _parse_radius_km(raw):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 5.0
    if value < 1:
        return 1.0
    if value > 50:
        return 50.0
    return value


def _to_rad(deg):
    return deg * math.pi / 180.0


def _distance_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    d_lat = _to_rad(b_lat - a_lat)
    d_lon = _to_rad(b_lon - a_lon)
    lat1 = _to_rad(a_lat)
    lat2 = _to_rad(b_lat)
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _within_radius_km(lat, lon, radius_km):
    if radius_km is None:
        return True
    return _distance_km(_DUBLIN_LAT, _DUBLIN_LON, lat, lon) <= radius_km


def _filter_points_within_radius(points, radius_km):
    if radius_km is None:
        return points
    filtered = []
    for p in points:
        lat = p.get("lat")
        lon = p.get("lon")
        if lat is None or lon is None:
            continue
        if _within_radius_km(lat, lon, radius_km):
            filtered.append(p)
    return filtered


def _build_bike_metrics(stations):
    if not stations:
        return None
    return {
        "available_bikes": sum(s.get("free_bikes", 0) for s in stations),
        "available_docks": sum(s.get("empty_slots", 0) for s in stations),
        "stations_reporting": len(stations),
    }


def _fetch_snapshot(backend_url, radius_km=5):
    try:
        resp = requests.get(
            f"{backend_url}/snapshot",
            params=[
                ("location", "dublin"),
                ("radius_km", f"{radius_km:g}"),
                ("lat", f"{_DUBLIN_LAT}"),
                ("lon", f"{_DUBLIN_LON}"),
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
        stops = data if isinstance(data, list) else []
        if stops:
            _BUS_STOP_CACHE.clear()
            _BUS_STOP_CACHE.extend(stops)
        return stops
    except Exception:
        return list(_BUS_STOP_CACHE)


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
            recs.append(
                {
                    "title": "High Traffic Congestion",
                    "description": "Significant traffic delays detected in Dublin city centre. "
                    "Consider using public transport or alternative routes.",
                    "priority": "High",
                    "source": "traffic",
                }
            )
        elif level == "medium":
            recs.append(
                {
                    "title": "Moderate Traffic Congestion",
                    "description": "Some traffic congestion in the area. Allow extra travel time if driving.",
                    "priority": "Medium",
                    "source": "traffic",
                }
            )
        total = traffic.get("total_incidents", 0)
        if total > 10:
            recs.append(
                {
                    "title": f"{total} Active Traffic Incidents",
                    "description": "Multiple traffic incidents reported. Check live traffic updates before travelling.",
                    "priority": "Medium",
                    "source": "traffic",
                }
            )

    if bikes:
        available = bikes.get("available_bikes", 0)
        if available < 10:
            recs.append(
                {
                    "title": "Low Bike Availability",
                    "description": f"Only {available} bikes available city-wide. Consider alternative transport.",
                    "priority": "High",
                    "source": "bikes",
                }
            )
        elif available > 100:
            recs.append(
                {
                    "title": "Good Bike Availability",
                    "description": f"{available} bikes available across the city. Great conditions for cycling!",
                    "priority": "Low",
                    "source": "bikes",
                }
            )

    if airquality:
        aqi = airquality.get("aqi_value")
        if aqi is not None:
            if aqi > 100:
                recs.append(
                    {
                        "title": "Poor Air Quality",
                        "description": f"Air Quality Index is {aqi}."
                        "Sensitive groups should avoid prolonged outdoor activity.",
                        "priority": "High",
                        "source": "air_quality",
                    }
                )
            elif aqi > 50:
                recs.append(
                    {
                        "title": "Moderate Air Quality",
                        "description": f"Air Quality Index is {aqi}. "
                        "Generally acceptable but may cause issues for very sensitive people.",
                        "priority": "Medium",
                        "source": "air_quality",
                    }
                )

    if not recs:
        recs.append(
            {
                "title": "All Clear",
                "description": "All city systems operating normally. No special advisories at this time.",
                "priority": "Low",
                "source": "system",
            }
        )

    return recs


@overview_bp.get("")
@overview_bp.get("/")
def dashboard():
    backend_url = current_app.config["BACKEND_API_URL"]
    radius_km = _parse_radius_km(request.args.get("radius_km"))
    snapshot, error = _fetch_snapshot(backend_url, radius_km)
    bike_stations = _fetch_bike_stations(backend_url)
    bike_stations = _filter_points_within_radius(bike_stations, radius_km)

    bikes = _build_bike_metrics(bike_stations) or snapshot.get("bikes")
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
        radius_km=radius_km,
    )


@overview_bp.get("/data")
def dashboard_data():
    backend_url = current_app.config["BACKEND_API_URL"]
    radius_km = _parse_radius_km(request.args.get("radius_km"))

    # Run all three slow fetches in parallel so the page loads faster
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_snapshot = pool.submit(_fetch_snapshot, backend_url, radius_km)
        f_bike_stations = pool.submit(_fetch_bike_stations, backend_url)
        f_bus_stops = pool.submit(_fetch_bus_stops, backend_url)

        snapshot, error = f_snapshot.result()
        bike_stations = _filter_points_within_radius(f_bike_stations.result(), radius_km)
        bus_stops = _filter_points_within_radius(f_bus_stops.result(), radius_km)

    bikes = _build_bike_metrics(bike_stations) or snapshot.get("bikes")

    recommendations = _build_recommendations(
        bikes,
        snapshot.get("traffic"),
        snapshot.get("airquality"),
    )
    return jsonify(
        {
            "timestamp": snapshot.get("timestamp"),
            "source_status": snapshot.get("source_status", {}),
            "bikes": bikes,
            "traffic": snapshot.get("traffic"),
            "airquality": snapshot.get("airquality"),
            "tours": snapshot.get("tours"),
            "bike_stations": bike_stations,
            "bus_stops": bus_stops,
            "recommendations": recommendations,
            "error": error,
        }
    )
