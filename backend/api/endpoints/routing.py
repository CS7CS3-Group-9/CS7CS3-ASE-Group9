"""
Backend routing endpoint — uses RoutesAdapter (Google Geocoding + Routes API v2).

GET /routing/calculate
  stops[]      : repeated, at least 2
  locked[]     : repeated bool per stop ("true"/"false")
  optimize     : "true" / "false"  (default true)
  mode         : driving | cycling | walking | transit
  type         : quickest | eco
  dep_time     : ISO datetime string e.g. "2026-02-19T14:30" (optional)
  arr_time     : ISO datetime string e.g. "2026-02-19T15:00" (optional, transit only)
"""
import re
from datetime import datetime
from itertools import permutations
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, jsonify, request

from backend.adapters.routes_adapter import RoutesAdapter, _ROUTES_URL
from backend.models.route_models import RouteRecommendation

routing_api_bp = Blueprint("routing_api", __name__, url_prefix="/routing")

_MAX_STOPS = 8

_GOOGLE_MODE = {
    "driving": "DRIVE",
    "cycling": "BICYCLE",
    "walking": "WALK",
    "transit": "TRANSIT",
}

# One shared adapter instance (reads GOOGLE_MAPS_API_KEY from env)
_adapter = RoutesAdapter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_duration_s(duration_str) -> int:
    return RoutesAdapter._parse_duration_s(duration_str)


def _strip_html(text) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _decode_polyline(encoded, precision=5):
    """Decode a Google encoded polyline to [[lat, lon], ...] list."""
    coords = []
    index = lat = lng = 0
    factor = 10 ** precision
    while index < len(encoded):
        for slot in range(2):
            shift = result = 0
            while True:
                if index >= len(encoded):
                    break
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            value = ~(result >> 1) if (result & 1) else (result >> 1)
            if slot == 0:
                lat += value
            else:
                lng += value
        coords.append([lat / factor, lng / factor])
    return coords


def _parse_datetime(s: str):
    """Parse a datetime-local string into a datetime object, or return None."""
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Google Routes API calls (using RoutesAdapter.route())
# ---------------------------------------------------------------------------

def _call_routes(ordered_coords, g_mode, dep_time=None, arr_time=None):
    """
    Route through an ordered list of (lat, lon) waypoints.
    Returns a frontend-compatible route dict or None.
    """
    if len(ordered_coords) < 2:
        return None

    field_mask = (
        "routes.duration,routes.distanceMeters,"
        "routes.polyline.encodedPolyline,"
        "routes.legs.steps.navigationInstruction,"
        "routes.legs.steps.distanceMeters,"
        "routes.legs.steps.staticDuration"
    )

    try:
        data = _adapter.route(
            origin=ordered_coords[0],
            destination=ordered_coords[-1],
            mode=g_mode,
            dep_time=dep_time,
            arr_time=arr_time,
            intermediates=ordered_coords[1:-1] or None,
            field_mask=field_mask,
        )
    except Exception:
        return None

    if "routes" not in data or not data["routes"]:
        return None

    r          = data["routes"][0]
    duration_s = _parse_duration_s(r.get("duration", "0s"))
    distance_m = r.get("distanceMeters", 0)

    encoded  = r.get("polyline", {}).get("encodedPolyline", "")
    coords   = _decode_polyline(encoded)
    geometry = {
        "type": "LineString",
        "coordinates": [[c[1], c[0]] for c in coords],
    }

    steps = []
    for leg in r.get("legs", []):
        for step in leg.get("steps", []):
            dist = step.get("distanceMeters", 0)
            dur  = _parse_duration_s(step.get("staticDuration", "0s"))
            nav  = step.get("navigationInstruction", {})
            instruction = _strip_html(nav.get("instructions", ""))
            if not instruction:
                continue
            steps.append({"instruction": instruction, "distance_m": dist, "duration_s": dur})

    return {
        "geometry":         geometry,
        "distance_meters":  distance_m,
        "distance_km":      round(distance_m / 1000, 2),
        "duration_seconds": duration_s,
        "duration_minutes": round(duration_s / 60),
        "steps":            steps[:50],
    }


def _call_transit(origin, destination, dep_time=None, arr_time=None):
    """
    Request a transit route via Google Routes API (TRANSIT mode).
    Returns (route_dict, error_str).
    """
    field_mask = (
        "routes.duration,routes.distanceMeters,"
        "routes.polyline.encodedPolyline,"
        "routes.legs.steps.travelMode,"
        "routes.legs.steps.distanceMeters,"
        "routes.legs.steps.staticDuration,"
        "routes.legs.steps.polyline.encodedPolyline,"
        "routes.legs.steps.transitDetails,"
        "routes.legs.steps.navigationInstruction"
    )
    try:
        data = _adapter.route(
            origin=origin,
            destination=destination,
            mode="TRANSIT",
            dep_time=dep_time,
            arr_time=arr_time,
            field_mask=field_mask,
        )
    except Exception as e:
        return None, f"Transit routing failed: {e}"

    if "routes" not in data or not data["routes"]:
        return None, "No transit route found for those locations."

    r          = data["routes"][0]
    duration_s = _parse_duration_s(r.get("duration", "0s"))
    distance_m = r.get("distanceMeters", 0)

    encoded    = r.get("polyline", {}).get("encodedPolyline", "")
    all_coords = _decode_polyline(encoded)
    geometry   = {
        "type": "LineString",
        "coordinates": [[c[1], c[0]] for c in all_coords],
    }

    legs_out = []
    for leg in r.get("legs", []):
        for step in leg.get("steps", []):
            travel_mode = step.get("travelMode", "WALK")
            dist = step.get("distanceMeters", 0)
            dur  = _parse_duration_s(step.get("staticDuration", "0s"))

            step_encoded = step.get("polyline", {}).get("encodedPolyline", "")
            step_coords  = _decode_polyline(step_encoded) if step_encoded else []

            td = step.get("transitDetails", {})
            if travel_mode == "TRANSIT" and td:
                stop_details = td.get("stopDetails", {})
                from_name    = stop_details.get("departureStop", {}).get("name", "")
                to_name      = stop_details.get("arrivalStop",   {}).get("name", "")
                tl           = td.get("transitLine", {})
                route_short  = tl.get("nameShort", "") or ""
                route_long   = tl.get("name", "")       or ""
                vt           = tl.get("vehicle", {}).get("type", "BUS").upper()
                mode_label   = (vt.replace("HEAVY_RAIL", "RAIL")
                                   .replace("LIGHT_RAIL", "TRAM")
                                   .replace("COMMUTER_TRAIN", "RAIL"))
            else:
                from_name   = _strip_html(step.get("navigationInstruction", {}).get("instructions", ""))
                to_name     = ""
                route_short = ""
                route_long  = ""
                mode_label  = "WALK"

            if not dist and not dur:
                continue
            legs_out.append({
                "mode":        mode_label,
                "from_name":   from_name,
                "to_name":     to_name,
                "duration_s":  dur,
                "distance_m":  dist,
                "route_short": route_short,
                "route_long":  route_long,
                "coords":      step_coords,
            })

    return {
        "legs":             legs_out,
        "geometry":         geometry,
        "distance_meters":  distance_m,
        "distance_km":      round(distance_m / 1000, 2),
        "duration_seconds": duration_s,
        "duration_minutes": round(duration_s / 60),
    }, None


# ---------------------------------------------------------------------------
# Stop-order optimisation (uses RoutesAdapter.route() for pair durations)
# ---------------------------------------------------------------------------

def _pair_duration(point_a, point_b, g_mode) -> float:
    """Travel time in seconds between two (lat, lon) points."""
    try:
        data = _adapter.route(
            origin=point_a,
            destination=point_b,
            mode=g_mode,
            field_mask="routes.duration",
        )
        if data.get("routes"):
            return float(_parse_duration_s(data["routes"][0].get("duration", "9999999s")))
    except Exception:
        pass
    return 9_999_999.0


def _build_time_matrix(waypoints, g_mode):
    n     = len(waypoints)
    times = [[0.0] * n for _ in range(n)]
    pairs = [(i, j) for i in range(n) for j in range(n) if i != j]

    def _fetch(pair):
        i, j = pair
        return i, j, _pair_duration(waypoints[i], waypoints[j], g_mode)

    with ThreadPoolExecutor(max_workers=min(12, len(pairs))) as pool:
        for i, j, t in pool.map(_fetch, pairs):
            times[i][j] = t
    return times


def _optimize_stop_order(all_coords, g_mode, locked):
    n          = len(all_coords)
    free_slots = [i for i in range(n) if not locked[i]]

    if len(free_slots) <= 1:
        return list(range(n))

    times          = _build_time_matrix(all_coords, g_mode)
    n_free         = len(free_slots)
    best_assign    = list(range(n_free))
    best_total     = float("inf")

    for perm in permutations(range(n_free)):
        route = list(range(n))
        for slot_idx, stop_idx in enumerate(perm):
            route[free_slots[slot_idx]] = free_slots[stop_idx]
        total = sum(times[route[k]][route[k + 1]] for k in range(n - 1))
        if total < best_total:
            best_total  = total
            best_assign = list(perm)

    ordered = list(range(n))
    for slot_idx, stop_idx in enumerate(best_assign):
        ordered[free_slots[slot_idx]] = free_slots[stop_idx]
    return ordered


# ---------------------------------------------------------------------------
# Flask endpoint
# ---------------------------------------------------------------------------

@routing_api_bp.get("/calculate")
def calculate():
    stops_raw = request.args.getlist("stops[]")

    if not stops_raw:
        o = request.args.get("origin", "").strip()
        d = request.args.get("destination", "").strip()
        if o and d:
            stops_raw = [o, d]

    stops_raw = [s.strip() for s in stops_raw if s.strip()]

    if len(stops_raw) < 2:
        return jsonify({"error": "At least an origin and destination are required."}), 400
    if len(stops_raw) > _MAX_STOPS:
        return jsonify({"error": f"Maximum {_MAX_STOPS} stops allowed."}), 400

    mode       = request.args.get("mode", "driving")
    route_type = request.args.get("type", "quickest")

    # Optional departure / arrival time
    dep_time = _parse_datetime(request.args.get("dep_time", ""))
    arr_time = _parse_datetime(request.args.get("arr_time", ""))
    if dep_time and arr_time:
        return jsonify({"error": "Specify either departure time or arrival time, not both."}), 400

    # Eco override: driving → cycling
    effective_mode = mode
    eco_note       = None
    if route_type == "eco" and mode == "driving":
        effective_mode = "cycling"
        eco_note       = "Switched to cycling for a lower-emission route."

    g_mode = _GOOGLE_MODE.get(effective_mode, "DRIVE")

    # Geocode every stop using RoutesAdapter
    geocoded = []
    for raw in stops_raw:
        try:
            lat, lon, display = _adapter.geocode(raw)
        except Exception:
            return jsonify({"error": f'Could not find location: "{raw}"'}), 400
        geocoded.append({"name": display, "lat": lat, "lon": lon, "input": raw})

    all_coords = [(g["lat"], g["lon"]) for g in geocoded]
    n_stops    = len(geocoded)

    # ---- Transit ----
    if effective_mode == "transit":
        route, err = _call_transit(
            all_coords[0], all_coords[-1],
            dep_time=dep_time, arr_time=arr_time,
        )
        if err:
            return jsonify({"error": err}), 502
        return jsonify({
            "stops":                  geocoded,
            "mode":                   "transit",
            "route_type":             route_type,
            "eco_note":               None,
            "route":                  route,
            "is_transit":             True,
            "waypoint_order_changed": False,
        })

    # ---- OSRM-style modes via Google Routes API ----
    optimize   = request.args.get("optimize", "true").lower() == "true"
    locked_raw = request.args.getlist("locked[]")

    if locked_raw and len(locked_raw) == n_stops:
        locked = [l.lower() == "true" for l in locked_raw]
    else:
        locked = [True] + [False] * max(0, n_stops - 2) + ([True] if n_stops > 1 else [])

    n_free           = sum(1 for l in locked if not l)
    original_indices = list(range(n_stops))
    ordered_indices  = original_indices[:]

    if optimize and n_free >= 2:
        ordered_indices = _optimize_stop_order(all_coords, g_mode, locked)

    ordered_coords   = [all_coords[i]  for i in ordered_indices]
    ordered_geocoded = [geocoded[i]    for i in ordered_indices]
    order_changed    = ordered_indices != original_indices

    try:
        route = _call_routes(ordered_coords, g_mode, dep_time=dep_time)
    except Exception as e:
        return jsonify({"error": f"Routing failed: {e}"}), 502

    if not route:
        return jsonify({"error": "No route found between those locations."}), 404

    return jsonify({
        "stops":                  ordered_geocoded,
        "origin":                 ordered_geocoded[0],
        "destination":            ordered_geocoded[-1],
        "mode":                   effective_mode,
        "route_type":             route_type,
        "eco_note":               eco_note,
        "route":                  route,
        "is_transit":             False,
        "waypoint_order_changed": order_changed,
    })
