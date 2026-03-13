import csv
import math
import time
from pathlib import Path
import requests
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, render_template, jsonify, current_app, request

overview_bp = Blueprint("overview", __name__, url_prefix="/dashboard")

_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603
_BUS_STOP_CACHE = {}
_BIKE_STATION_CACHE = {}
_SNAPSHOT_CACHE = {}
_NEEDS_CACHE = {}
_CACHE_TTLS = {
    "bus_stops": 300.0,
    "bike_stations": 60.0,
    "snapshot": 30.0,
    "needs": 300.0,
}
_BUS_NEEDS_THRESHOLD_KM = 0.6
_BIKE_NEEDS_THRESHOLD_KM = 1.0
_MAX_NEEDS_MARKERS = 5
_MIN_NEEDS_MARKERS = 3
_POPULATION_CENTRES_FALLBACK = [
    {"name": "Smithfield", "lat": 53.3473, "lon": -6.2783, "population_weight": 1.0},
    {"name": "Docklands", "lat": 53.3469, "lon": -6.2397, "population_weight": 1.0},
    {"name": "The Liberties", "lat": 53.3430, "lon": -6.2800, "population_weight": 0.95},
    {"name": "Phibsborough", "lat": 53.3609, "lon": -6.2722, "population_weight": 0.9},
    {"name": "Ringsend", "lat": 53.3417, "lon": -6.2264, "population_weight": 0.85},
    {"name": "Inchicore", "lat": 53.3395, "lon": -6.3174, "population_weight": 0.85},
    {"name": "Drimnagh", "lat": 53.3350, "lon": -6.3128, "population_weight": 0.8},
    {"name": "Harold's Cross", "lat": 53.3298, "lon": -6.2849, "population_weight": 0.8},
    {"name": "Rathmines", "lat": 53.3240, "lon": -6.2651, "population_weight": 0.9},
    {"name": "Drumcondra", "lat": 53.3706, "lon": -6.2527, "population_weight": 0.9},
    {"name": "Finglas", "lat": 53.3893, "lon": -6.2966, "population_weight": 0.85},
    {"name": "Crumlin", "lat": 53.3216, "lon": -6.3170, "population_weight": 0.85},
    {"name": "Raheny", "lat": 53.3803, "lon": -6.1774, "population_weight": 0.85},
    {"name": "Donnybrook", "lat": 53.3213, "lon": -6.2365, "population_weight": 0.8},
    {"name": "Cabra", "lat": 53.3659, "lon": -6.2969, "population_weight": 0.85},
    {"name": "Ballyfermot", "lat": 53.3446, "lon": -6.3540, "population_weight": 0.85},
    {"name": "Coolock", "lat": 53.3902, "lon": -6.2013, "population_weight": 0.85},
    {"name": "Terenure", "lat": 53.3097, "lon": -6.2856, "population_weight": 0.8},
    {"name": "Blanchardstown", "lat": 53.3880, "lon": -6.3755, "population_weight": 1.0},
    {"name": "Tallaght", "lat": 53.2867, "lon": -6.3731, "population_weight": 1.0},
    {"name": "Swords", "lat": 53.4597, "lon": -6.2181, "population_weight": 0.9},
    {"name": "Clondalkin", "lat": 53.3242, "lon": -6.3970, "population_weight": 0.8},
    {"name": "Balbriggan", "lat": 53.6121, "lon": -6.1833, "population_weight": 0.7},
]
_POPULATION_CENTRES_CACHE = None
_MAX_POPULATION_CENTRES = 300


def _load_population_centres_from_csv():
    repo_root = Path(__file__).resolve().parents[2]
    csv_path = repo_root / "data" / "historical" / "population_data_with_coords.csv"
    if not csv_path.exists():
        return None

    centres_by_name = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("BUA_NAME") != "Dublin city and suburbs":
                continue
            name = (row.get("ED_ENGLISH") or "").strip()
            if not name:
                continue
            try:
                lat = float(row.get("Latitude") or "")
                lon = float(row.get("Longitude") or "")
                population = float(row.get("T9_1_TT") or 0)
            except ValueError:
                continue
            record = centres_by_name.get(name)
            if record is None:
                centres_by_name[name] = {
                    "name": name,
                    "lat_sum": lat * population,
                    "lon_sum": lon * population,
                    "population": population,
                }
            else:
                record["lat_sum"] += lat * population
                record["lon_sum"] += lon * population
                record["population"] += population

    if not centres_by_name:
        return None

    max_population = max(c["population"] for c in centres_by_name.values())
    centres = []
    for record in centres_by_name.values():
        population = record["population"]
        if population <= 0:
            continue
        centres.append(
            {
                "name": record["name"],
                "lat": record["lat_sum"] / population,
                "lon": record["lon_sum"] / population,
                "population_weight": population / max_population,
            }
        )

    centres.sort(key=lambda x: x["population_weight"], reverse=True)
    return centres[:_MAX_POPULATION_CENTRES]


def _get_population_centres():
    global _POPULATION_CENTRES_CACHE
    if _POPULATION_CENTRES_CACHE is not None:
        return _POPULATION_CENTRES_CACHE

    centres = _load_population_centres_from_csv()
    if not centres:
        centres = list(_POPULATION_CENTRES_FALLBACK)
    _POPULATION_CENTRES_CACHE = centres
    return centres


def _cache_get(cache, key, ttl_seconds):
    entry = cache.get(key)
    if entry is None:
        return None
    if time.time() - entry["timestamp"] > ttl_seconds:
        return None
    return entry["data"]


def _cache_set(cache, key, data):
    cache[key] = {"timestamp": time.time(), "data": data}


def _cache_get_stale(cache, key):
    entry = cache.get(key)
    if entry is None:
        return None
    return entry["data"]


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


def _nearest_distance_km(target_lat, target_lon, points):
    nearest = None
    for p in points or []:
        lat = p.get("lat")
        lon = p.get("lon")
        if lat is None or lon is None:
            continue
        d = _distance_km(target_lat, target_lon, lat, lon)
        if nearest is None or d < nearest:
            nearest = d
    return nearest


def _max_distance_from_centre_km(points):
    max_d = None
    for p in points or []:
        lat = p.get("lat")
        lon = p.get("lon")
        if lat is None or lon is None:
            continue
        d = _distance_km(_DUBLIN_LAT, _DUBLIN_LON, lat, lon)
        if max_d is None or d > max_d:
            max_d = d
    return max_d


def _tracked_overlap_km(bus_stops, bike_stations):
    max_bus_km = _max_distance_from_centre_km(bus_stops)
    max_bike_km = _max_distance_from_centre_km(bike_stations)
    if max_bus_km is not None and max_bike_km is not None:
        return min(max_bus_km, max_bike_km)
    return None


def _needs_access_areas(kind, bus_stops, bike_stations, radius_km, threshold_km):
    needs = []
    candidates = []
    tracked_km = (
        _max_distance_from_centre_km(bus_stops) if kind == "bus" else _max_distance_from_centre_km(bike_stations)
    )

    for c in _get_population_centres():
        centre_from_dublin_km = _distance_km(_DUBLIN_LAT, _DUBLIN_LON, c["lat"], c["lon"])
        if tracked_km is not None and centre_from_dublin_km > tracked_km:
            continue
        bus_km = _nearest_distance_km(c["lat"], c["lon"], bus_stops)
        bike_km = _nearest_distance_km(c["lat"], c["lon"], bike_stations)
        if kind == "bus" and bus_km is None:
            continue
        if kind == "bike" and bike_km is None:
            continue
        if radius_km is not None and not _within_radius_km(c["lat"], c["lon"], radius_km):
            continue
        distance_km = bus_km if kind == "bus" else bike_km
        if distance_km is None:
            continue
        if bus_km is None:
            bus_km = distance_km
        if bike_km is None:
            bike_km = distance_km
        item = {
            "kind": kind,
            "name": c["name"],
            "lat": c["lat"],
            "lon": c["lon"],
            "bus_km": bus_km,
            "bike_km": bike_km,
            "score": (bus_km * 0.6 + bike_km * 0.4) * c["population_weight"],
        }
        candidates.append(item)
        if distance_km > threshold_km:
            needs.append(item)

    # Keep multiple markers visible: fill to a minimum count using top distances.
    if len(needs) < _MIN_NEEDS_MARKERS and candidates:
        used = {(n["name"], n["lat"], n["lon"]) for n in needs}
        remaining = [
            c
            for c in sorted(
                candidates,
                key=lambda x: x["bus_km"] if kind == "bus" else x["bike_km"],
                reverse=True,
            )
            if (c["name"], c["lat"], c["lon"]) not in used
        ]
        take = _MIN_NEEDS_MARKERS - len(needs)
        needs.extend(remaining[:take])

    needs.sort(key=lambda x: x["bus_km"] if kind == "bus" else x["bike_km"], reverse=True)
    return needs[:_MAX_NEEDS_MARKERS]


def _needs_bus_areas(bus_stops, bike_stations, radius_km):
    return _needs_access_areas(
        kind="bus",
        bus_stops=bus_stops,
        bike_stations=bike_stations,
        radius_km=radius_km,
        threshold_km=_BUS_NEEDS_THRESHOLD_KM,
    )


def _needs_bike_areas(bus_stops, bike_stations, radius_km):
    return _needs_access_areas(
        kind="bike",
        bus_stops=bus_stops,
        bike_stations=bike_stations,
        radius_km=radius_km,
        threshold_km=_BIKE_NEEDS_THRESHOLD_KM,
    )


def _fetch_snapshot(backend_url, radius_km=5, include=None):
    include = include or ["bikes", "traffic", "airquality", "tours", "buses"]
    cache_key = f"{backend_url}|{radius_km:g}|{','.join(include)}"
    cached = _cache_get(_SNAPSHOT_CACHE, cache_key, _CACHE_TTLS["snapshot"])
    if cached is not None:
        return cached, None
    try:
        resp = requests.get(
            f"{backend_url}/snapshot",
            params=[
                ("location", "dublin"),
                ("radius_km", f"{radius_km:g}"),
                ("lat", f"{_DUBLIN_LAT}"),
                ("lon", f"{_DUBLIN_LON}"),
                *[("include", item) for item in include],
            ],
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        _cache_set(_SNAPSHOT_CACHE, cache_key, data)
        return data, None
    except Exception as e:
        stale = _cache_get_stale(_SNAPSHOT_CACHE, cache_key)
        if stale is not None:
            return stale, None
        return {}, str(e)


def _fetch_bus_stops(backend_url, radius_km=None):
    """Fetch Dublin bus stops from the backend."""
    cache_key = f"{backend_url}|{radius_km or 'default'}"
    cached = _cache_get(_BUS_STOP_CACHE, cache_key, _CACHE_TTLS["bus_stops"])
    if cached is not None:
        return cached

    try:
        params = {
            "lat": f"{_DUBLIN_LAT}",
            "lon": f"{_DUBLIN_LON}",
        }
        if radius_km is not None:
            params["radius_km"] = f"{radius_km:g}"
        resp = requests.get(f"{backend_url}/buses/stops", params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        stops = data if isinstance(data, list) else []
        if stops:
            _cache_set(_BUS_STOP_CACHE, cache_key, stops)
        return stops
    except Exception:
        stale = _cache_get_stale(_BUS_STOP_CACHE, cache_key)
        return stale if stale is not None else []


def _fetch_bike_stations(backend_url, radius_km=None):
    """Fetch per-station Dublin Bikes data from the backend."""
    cache_key = f"{backend_url}|{radius_km or 'default'}"
    cached = _cache_get(_BIKE_STATION_CACHE, cache_key, _CACHE_TTLS["bike_stations"])
    if cached is not None:
        return cached

    try:
        params = {
            "lat": f"{_DUBLIN_LAT}",
            "lon": f"{_DUBLIN_LON}",
        }
        if radius_km is not None:
            params["radius_km"] = f"{radius_km:g}"
        resp = requests.get(f"{backend_url}/bikes/stations", params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        stations = data if isinstance(data, list) else []
        if stations:
            _cache_set(_BIKE_STATION_CACHE, cache_key, stations)
        return stations
    except Exception:
        stale = _cache_get_stale(_BIKE_STATION_CACHE, cache_key)
        return stale if stale is not None else []


def _get_needs_cached(bus_stops, bike_stations, radius_km):
    key = (radius_km, len(bus_stops), len(bike_stations))
    cached = _cache_get(_NEEDS_CACHE, key, _CACHE_TTLS["needs"])
    if cached is not None:
        return cached["bus"], cached["bike"]

    needs_bus = _needs_bus_areas(bus_stops, bike_stations, radius_km)
    needs_bike = _needs_bike_areas(bus_stops, bike_stations, radius_km)
    _cache_set(_NEEDS_CACHE, key, {"bus": needs_bus, "bike": needs_bike})
    return needs_bus, needs_bike


def _build_recommendations(
    bikes,
    traffic,
    airquality,
    bike_stations=None,
    bus_stops=None,
    radius_km=None,
):
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

    needs_bus, needs_bike = _get_needs_cached(bus_stops or [], bike_stations or [], radius_km)
    if needs_bus:
        top = needs_bus[0]
        recs.append(
            {
                "title": "Add Bus Stop Coverage In Priority Area",
                "description": (
                    f"{top['name']} has weak bus access: nearest bus stop is {top['bus_km']:.1f} km away. "
                    f"Prioritise a new bus stop or route extension in this area."
                ),
                "priority": "High",
                "source": "planning",
            }
        )
        if len(needs_bus) > 1:
            second = needs_bus[1]
            recs.append(
                {
                    "title": "Second Bus Access Priority",
                    "description": (
                        f"Next bus-stop upgrade target: {second['name']} "
                        f"(nearest bus stop {second['bus_km']:.1f} km)."
                    ),
                    "priority": "Medium",
                    "source": "planning",
                }
            )

    if needs_bike:
        top = needs_bike[0]
        recs.append(
            {
                "title": "Add Bike Station Coverage In Priority Area",
                "description": (
                    f"{top['name']} has weak bike access: nearest bike station is {top['bike_km']:.1f} km away. "
                    "Prioritise a new bike station in this area."
                ),
                "priority": "High",
                "source": "planning",
            }
        )
        if len(needs_bike) > 1:
            second = needs_bike[1]
            recs.append(
                {
                    "title": "Second Bike Access Priority",
                    "description": (
                        f"Next bike-station upgrade target: {second['name']} "
                        f"(nearest bike station {second['bike_km']:.1f} km)."
                    ),
                    "priority": "Medium",
                    "source": "planning",
                }
            )

    if traffic and bikes:
        if traffic.get("congestion_level") == "high" and bikes.get("available_bikes", 0) < 40:
            recs.append(
                {
                    "title": "Shift Short Trips Away From Cars",
                    "description": (
                        "High congestion and low bike supply detected. "
                        "Temporarily rebalance bikes toward dense commuter corridors "
                        "and add temporary bus priority where delays are highest."
                    ),
                    "priority": "High",
                    "source": "planning",
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
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_snapshot = pool.submit(_fetch_snapshot, backend_url, radius_km)
        f_bike_stations = pool.submit(_fetch_bike_stations, backend_url, radius_km)
        f_bus_stops = pool.submit(_fetch_bus_stops, backend_url, radius_km)

        snapshot, error = f_snapshot.result()
        bike_stations = f_bike_stations.result()
        bus_stops = f_bus_stops.result()

    bikes = _build_bike_metrics(bike_stations) or snapshot.get("bikes")
    traffic = snapshot.get("traffic")
    airquality = snapshot.get("airquality")
    tours = snapshot.get("tours")
    timestamp = snapshot.get("timestamp")
    source_status = snapshot.get("source_status", {})
    recommendations = _build_recommendations(
        bikes,
        traffic,
        airquality,
        bike_stations=bike_stations,
        bus_stops=bus_stops,
        radius_km=radius_km,
    )

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
        f_bike_stations = pool.submit(_fetch_bike_stations, backend_url, radius_km)
        f_bus_stops = pool.submit(_fetch_bus_stops, backend_url, radius_km)

        snapshot, error = f_snapshot.result()
        bike_stations = f_bike_stations.result()
        bus_stops = f_bus_stops.result()

    bikes = _build_bike_metrics(bike_stations) or snapshot.get("bikes")

    needs_bus_areas, needs_bike_areas = _get_needs_cached(bus_stops, bike_stations, radius_km)
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
            "needs_bus_areas": needs_bus_areas,
            "needs_bike_areas": needs_bike_areas,
            "error": error,
        }
    )
