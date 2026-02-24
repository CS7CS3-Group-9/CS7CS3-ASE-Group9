"""
Backend bus-stops endpoint.

GET /buses/stops
  Returns Dublin bus stops near city centre from OpenStreetMap Overpass API.
"""
import requests
from flask import Blueprint, jsonify

buses_bp = Blueprint("buses", __name__, url_prefix="/buses")

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603
_RADIUS_M = 5000


@buses_bp.get("/stops")
def bus_stops():
    """Return bus stops near Dublin city centre."""
    query = (
        f"[out:json];"
        f'node["highway"="bus_stop"](around:{_RADIUS_M},{_DUBLIN_LAT},{_DUBLIN_LON});'
        f"out;"
    )
    try:
        resp = requests.post(_OVERPASS_URL, data=query, timeout=20)
        resp.raise_for_status()
        stops = []
        for e in resp.json().get("elements", []):
            if "lat" not in e or "lon" not in e:
                continue
            tags = e.get("tags", {})
            stops.append({
                "name": tags.get("name") or tags.get("ref") or "Bus Stop",
                "lat": e["lat"],
                "lon": e["lon"],
                "ref": tags.get("ref", ""),
                "routes": tags.get("route_ref", ""),
            })
        return jsonify(stops)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
