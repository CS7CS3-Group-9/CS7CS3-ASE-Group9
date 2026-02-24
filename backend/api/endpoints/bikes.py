import requests
from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.bikes_adapter import BikesAdapter

bikes_bp = Blueprint("bikes", __name__)

_CITYBIKES_URL = "https://api.citybik.es/v2/networks/dublinbikes"


@bikes_bp.get("/bikes")
def get_bikes():
    location = request.args.get("location", "dublin")

    service = SnapshotService(adapter_specs=[AdapterCallSpec(adapter=BikesAdapter(), kwargs={})])
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))


@bikes_bp.get("/bikes/stations")
def get_bike_stations():
    """Return per-station Dublin Bikes data for map display."""
    try:
        resp = requests.get(_CITYBIKES_URL, timeout=5)
        resp.raise_for_status()
        stations = resp.json()["network"]["stations"]
        return jsonify([
            {
                "name": s["name"],
                "lat": s["latitude"],
                "lon": s["longitude"],
                "free_bikes": s["free_bikes"],
                "empty_slots": s["empty_slots"],
                "total": s["extra"]["slots"],
            }
            for s in stations
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 502
