"""
Fleet Efficiency endpoint — Vehicle Routing Problem solver with scoring.

POST /routing/efficiency
  JSON body:
    stops        : list of address strings or {"name", "lat", "lon"} objects  (1-20)
    vehicles     : int  1-10  (default 1)
    mode         : driving | cycling | walking  (default driving)

  OR to score an existing fleet plan:
    existing_routes : list of lists of address strings / coord objects
    mode            : as above

Returns:
  routes       : [{vehicle, stops, distance_km, duration_min, geometry}, ...]
  score        : 0-100 efficiency score
  suggestions  : list of improvement strings
  total_distance_km
  n_vehicles / n_stops
"""
import math
from flask import Blueprint, jsonify, request

from backend.api.endpoints.routing import (
    _adapter, _call_routes, _call_local_route, _GOOGLE_MODE, _geocode_nominatim,
)

efficiency_bp = Blueprint("efficiency_api", __name__, url_prefix="/routing")

_MAX_STOPS = 20
_VEHICLE_COLOURS = [
    "#2563eb", "#16a34a", "#dc2626", "#d97706",
    "#7c3aed", "#0891b2", "#c2410c", "#65a30d",
    "#9333ea", "#0284c7",
]


# ---------------------------------------------------------------------------
# Distance helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _dist_matrix(coords):
    n = len(coords)
    d = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            v = _haversine_km(coords[i][0], coords[i][1],
                              coords[j][0], coords[j][1])
            d[i][j] = d[j][i] = v
    return d


# ---------------------------------------------------------------------------
# VRP solver: nearest-neighbour clustering + 2-opt improvement
# ---------------------------------------------------------------------------

def _vrp_nearest_neighbour(dist, n_stops, n_vehicles):
    """
    Partition stops into n_vehicles routes using a balanced nearest-neighbour
    strategy.  Each vehicle starts from a different 'seed' stop chosen to
    spread vehicles across the network.
    """
    target = [n_stops // n_vehicles + (1 if i < n_stops % n_vehicles else 0)
              for i in range(n_vehicles)]
    routes = [[] for _ in range(n_vehicles)]
    unvisited = list(range(n_stops))

    # Seed: vehicle 0 takes stop 0, each subsequent vehicle takes the stop
    # furthest from all existing seeds.
    for v in range(n_vehicles):
        if not unvisited:
            break
        if v == 0:
            seed = 0
        else:
            seeds = [routes[k][0] for k in range(v) if routes[k]]
            seed = max(unvisited,
                       key=lambda s: min(dist[s][st] for st in seeds))
        routes[v].append(seed)
        unvisited.remove(seed)

    # Greedily assign remaining stops to the vehicle whose last stop is nearest,
    # respecting target sizes.
    while unvisited:
        needs = [v for v in range(n_vehicles) if len(routes[v]) < target[v]]
        if not needs:
            # overflow: append to least-loaded vehicle
            needs = [min(range(n_vehicles), key=lambda v: len(routes[v]))]

        best_v = best_s = None
        best_d = float("inf")
        for v in needs:
            last = routes[v][-1] if routes[v] else 0
            for s in unvisited:
                d = dist[last][s]
                if d < best_d:
                    best_d, best_v, best_s = d, v, s

        routes[best_v].append(best_s)
        unvisited.remove(best_s)

    return routes


def _two_opt(route, dist):
    """2-opt improvement for an open (non-circular) route."""
    n = len(route)
    if n < 4:
        return route
    improved = True
    while improved:
        improved = False
        for i in range(n - 2):
            for j in range(i + 2, n - 1):
                before = dist[route[i]][route[i + 1]] + dist[route[j]][route[j + 1]]
                after  = dist[route[i]][route[j]]     + dist[route[i + 1]][route[j + 1]]
                if after < before - 1e-9:
                    route[i + 1: j + 1] = route[i + 1: j + 1][::-1]
                    improved = True
    return route


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score(vehicle_routes, dist):
    """
    Returns (score 0-100, vehicle_distances list).

    score = 40*balance + 40*routing_quality + 20*utilization
    """
    vehicle_distances = []
    for route in vehicle_routes:
        if len(route) <= 1:
            vehicle_distances.append(0.0)
        else:
            vehicle_distances.append(
                sum(dist[route[i]][route[i + 1]] for i in range(len(route) - 1))
            )

    n_vehicles = len(vehicle_routes)
    active = [d for d in vehicle_distances if d > 0.0]

    # -- Balance (40 pts): coefficient of variation of vehicle distances --
    if len(active) > 1:
        mean = sum(active) / len(active)
        std  = (sum((d - mean) ** 2 for d in active) / len(active)) ** 0.5
        cv   = std / mean if mean > 0 else 0.0
        balance = max(0.0, 1.0 - cv)
    else:
        balance = 1.0

    # -- Routing quality (40 pts): circuity of each vehicle's route --
    # circuity = path_length / start-to-end distance  (1.0 = perfectly direct)
    circuities = []
    for route in vehicle_routes:
        if len(route) < 2:
            continue
        path   = sum(dist[route[i]][route[i + 1]] for i in range(len(route) - 1))
        direct = dist[route[0]][route[-1]]
        circuities.append(min(2.0, path / direct) if direct > 0 else 1.0)
    if circuities:
        avg_circ = sum(circuities) / len(circuities)
        routing_quality = max(0.0, 1.0 - (avg_circ - 1.0))
    else:
        routing_quality = 1.0

    # -- Utilization (20 pts): fraction of vehicles that have at least one stop --
    utilization = len(active) / n_vehicles if n_vehicles > 0 else 1.0

    score = round(40 * balance + 40 * routing_quality + 20 * utilization)
    return max(0, min(100, score)), vehicle_distances


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

def _suggestions(vehicle_routes, geocoded, vehicle_distances, dist):
    tips = []
    n_v  = len(vehicle_routes)

    # Empty vehicles
    empty = [i + 1 for i, r in enumerate(vehicle_routes) if not r]
    if empty:
        optimal = n_v - len(empty)
        tips.append(
            f"{len(empty)} vehicle(s) have no stops assigned — "
            f"reducing to {max(1, optimal)} vehicle(s) would be more efficient."
        )

    # Imbalanced load
    active = [(i, vehicle_distances[i]) for i, r in enumerate(vehicle_routes) if r]
    if len(active) >= 2:
        hi = max(active, key=lambda x: x[1])
        lo = min(active, key=lambda x: x[1])
        if lo[1] > 0 and hi[1] > lo[1] * 1.5:
            tips.append(
                f"Vehicle {hi[0]+1} covers {hi[1]:.1f} km but "
                f"Vehicle {lo[0]+1} covers only {lo[1]:.1f} km — "
                f"redistributing stops could improve balance."
            )

    # Stops on different vehicles that are very close together
    for v1 in range(n_v):
        for v2 in range(v1 + 1, n_v):
            for s1 in vehicle_routes[v1]:
                for s2 in vehicle_routes[v2]:
                    if dist[s1][s2] < 0.4:
                        tips.append(
                            f"'{geocoded[s1]['name']}' and '{geocoded[s2]['name']}' "
                            f"are {dist[s1][s2]*1000:.0f} m apart but assigned to "
                            f"different vehicles — consider consolidating."
                        )
                        break

    # Longest single leg
    all_legs = []
    for v, route in enumerate(vehicle_routes):
        for i in range(len(route) - 1):
            all_legs.append((dist[route[i]][route[i + 1]], v, route[i], route[i + 1]))
    if all_legs:
        longest = max(all_legs, key=lambda x: x[0])
        if longest[0] > 3.0:
            tips.append(
                f"Longest leg: '{geocoded[longest[2]]['name']}' → "
                f"'{geocoded[longest[3]]['name']}' "
                f"({longest[0]:.1f} km, Vehicle {longest[1]+1}) — "
                f"a stop between these two locations could cut this leg significantly."
            )

    # High-circuity vehicle
    for v, route in enumerate(vehicle_routes):
        if len(route) < 3:
            continue
        path   = vehicle_distances[v]
        direct = dist[route[0]][route[-1]]
        if direct > 0 and path / direct > 1.6:
            tips.append(
                f"Vehicle {v+1}'s route backtracks significantly "
                f"({path:.1f} km driven vs {direct:.1f} km start-to-end) — "
                f"reordering its stops could reduce distance."
            )

    if not tips:
        tips.append("The fleet plan looks well-optimised for the given stops and vehicles.")

    return tips[:5]


# ---------------------------------------------------------------------------
# Geocoding helper (re-uses shared adapter)
# ---------------------------------------------------------------------------

def _geocode_stop(raw) -> dict:
    """
    Return {"name", "lat", "lon"} or raise ValueError.
    Pin-drop objects {lat, lon} bypass geocoding entirely (works fully offline).
    For text addresses: tries Google first, falls back to Nominatim (OSM, no key needed).
    """
    if isinstance(raw, dict) and "lat" in raw and "lon" in raw:
        return {
            "name": raw.get("name", f"{raw['lat']:.4f},{raw['lon']:.4f}"),
            "lat":  float(raw["lat"]),
            "lon":  float(raw["lon"]),
        }
    # Try Google geocoding first
    try:
        lat, lon, display = _adapter.geocode(str(raw))
        return {"name": display, "lat": lat, "lon": lon}
    except Exception:
        pass
    # Fall back to Nominatim (OpenStreetMap — no API key required)
    lat, lon, display = _geocode_nominatim(str(raw))
    return {"name": display, "lat": lat, "lon": lon}


# ---------------------------------------------------------------------------
# Route geometry helper — Google first, then chain local router per segment
# ---------------------------------------------------------------------------

def _get_geometry(ordered_coords, g_mode, transport):
    """
    Try Google Routes for the full multi-stop path.
    Fall back to chaining local SUMO router calls segment-by-segment so
    route lines always appear even without a Google API key.
    """
    if len(ordered_coords) < 2:
        return None

    # Google attempt (handles multi-stop natively)
    route = _call_routes(ordered_coords, g_mode)
    if route:
        return route

    # Local fallback — only supported for driving within the Dublin network
    if transport != "driving":
        return None

    all_coords: list = []
    total_dist = 0
    total_dur  = 0
    for i in range(len(ordered_coords) - 1):
        seg = _call_local_route(ordered_coords[i], ordered_coords[i + 1])
        if seg:
            all_coords.extend(seg["geometry"]["coordinates"])
            total_dist += seg["distance_meters"]
            total_dur  += seg["duration_seconds"]

    if not all_coords:
        return None

    return {
        "geometry":         {"type": "LineString", "coordinates": all_coords},
        "distance_meters":  total_dist,
        "distance_km":      round(total_dist / 1000, 2),
        "duration_seconds": total_dur,
        "duration_minutes": round(total_dur / 60),
        "local_fallback":   True,
    }


# ---------------------------------------------------------------------------
# Flask endpoint
# ---------------------------------------------------------------------------

def _geocode_depot(raw):
    """Geocode optional start/end depot. Returns stop dict or None."""
    if not raw:
        return None
    try:
        return _geocode_stop(raw)
    except Exception:
        raise


def _build_vehicle_output(vehicle_routes, geocoded, start_stop, end_stop,
                           g_mode, transport):
    """
    For each vehicle route (list of indices into geocoded), prepend/append
    the depot stops if provided, get geometry, and return the routes_out list
    plus vehicle_distances.
    """
    routes_out        = []
    vehicle_distances = []

    for v, route in enumerate(vehicle_routes):
        veh_stops = [geocoded[i] for i in route]
        full_stops = (([start_stop] if start_stop else []) +
                      veh_stops +
                      ([end_stop]   if end_stop   else []))

        ordered_coords = [(s["lat"], s["lon"]) for s in full_stops]
        dist_km = sum(
            _haversine_km(ordered_coords[i][0], ordered_coords[i][1],
                          ordered_coords[i + 1][0], ordered_coords[i + 1][1])
            for i in range(len(ordered_coords) - 1)
        ) if len(ordered_coords) > 1 else 0.0
        vehicle_distances.append(dist_km)

        route_data = _get_geometry(ordered_coords, g_mode, transport) if len(ordered_coords) >= 2 else None
        routes_out.append({
            "vehicle":      v + 1,
            "colour":       _VEHICLE_COLOURS[v % len(_VEHICLE_COLOURS)],
            "stops":        full_stops,
            "distance_km":  round(dist_km, 2),
            "duration_min": (round(route_data["duration_minutes"]) if route_data else None),
            "geometry":     route_data["geometry"] if route_data else None,
        })

    return routes_out, vehicle_distances


@efficiency_bp.post("/efficiency")
def efficiency():
    data      = request.get_json(force=True) or {}
    action    = data.get("action", "analyse")   # "build" | "analyse"
    transport = data.get("transport", data.get("mode", "driving"))
    g_mode    = _GOOGLE_MODE.get(transport, "DRIVE")

    # Optional depot for both modes
    start_stop = end_stop = None
    if data.get("start"):
        try:
            start_stop = _geocode_depot(data["start"])
        except Exception:
            return jsonify({"error": f'Could not find start: "{data["start"]}"'}), 400
    if data.get("end"):
        try:
            end_stop = _geocode_depot(data["end"])
        except Exception:
            return jsonify({"error": f'Could not find end: "{data["end"]}"'}), 400

    # ================================================================
    # BUILD mode — flat stop list, VRP assigns them to vehicles.
    # ================================================================
    if action == "build":
        stops_raw  = data.get("stops", [])
        n_vehicles = max(1, min(10, int(data.get("vehicles", 1))))

        if not stops_raw:
            return jsonify({"error": "Please add at least one stop."}), 400
        if len(stops_raw) > _MAX_STOPS:
            return jsonify({"error": f"Maximum {_MAX_STOPS} stops."}), 400

        geocoded = []
        for raw in stops_raw:
            try:
                geocoded.append(_geocode_stop(raw))
            except Exception:
                return jsonify({"error": f'Could not find location: "{raw}"'}), 400

        n_vehicles     = min(n_vehicles, len(geocoded))
        coords         = [(g["lat"], g["lon"]) for g in geocoded]
        dist           = _dist_matrix(coords)
        vehicle_routes = _vrp_nearest_neighbour(dist, len(geocoded), n_vehicles)
        vehicle_routes = [_two_opt(r, dist) for r in vehicle_routes]

        score, vehicle_distances_inner = _score(vehicle_routes, dist)
        tips = _suggestions(vehicle_routes, geocoded, vehicle_distances_inner, dist)

        routes_out, vehicle_distances = _build_vehicle_output(
            vehicle_routes, geocoded, start_stop, end_stop, g_mode, transport)

        return jsonify({
            "routes":             routes_out,
            "score":              score,
            "suggestions":        tips,
            "total_distance_km":  round(sum(vehicle_distances), 2),
            "n_vehicles":         n_vehicles,
            "n_stops":            len(geocoded),
        })

    # ================================================================
    # ANALYSE mode — score existing per-vehicle routes as given.
    # ================================================================
    existing = data.get("existing_routes", [])
    if not existing:
        return jsonify({"error": "Provide 'existing_routes' (list of lists of stops)."}), 400

    all_raw = [s for veh in existing for s in veh]
    if not all_raw:
        return jsonify({"error": "No stops provided."}), 400
    if len(all_raw) > _MAX_STOPS:
        return jsonify({"error": f"Maximum {_MAX_STOPS} stops."}), 400

    geocoded = []
    for raw in all_raw:
        try:
            geocoded.append(_geocode_stop(raw))
        except Exception:
            return jsonify({"error": f'Could not find location: "{raw}"'}), 400

    idx = 0
    vehicle_routes = []
    for veh in existing:
        vehicle_routes.append(list(range(idx, idx + len(veh))))
        idx += len(veh)
    n_vehicles = len(vehicle_routes)

    coords = [(g["lat"], g["lon"]) for g in geocoded]
    dist   = _dist_matrix(coords)
    score, vehicle_distances_inner = _score(vehicle_routes, dist)
    tips   = _suggestions(vehicle_routes, geocoded, vehicle_distances_inner, dist)

    routes_out, vehicle_distances = _build_vehicle_output(
        vehicle_routes, geocoded, start_stop, end_stop, g_mode, transport)

    return jsonify({
        "routes":             routes_out,
        "score":              score,
        "suggestions":        tips,
        "total_distance_km":  round(sum(vehicle_distances), 2),
        "n_vehicles":         n_vehicles,
        "n_stops":            len(geocoded),
    })
