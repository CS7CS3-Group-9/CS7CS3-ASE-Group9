from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.traffic_adapter import TrafficAdapter

traffic_bp = Blueprint("traffic", __name__)


@traffic_bp.get("/traffic")
def get_traffic():
    location = request.args.get("location", "dublin")
    try:
        radius_km = float(request.args.get("radius_km", "1.0"))
    except ValueError:
        radius_km = 1.0

    service = SnapshotService(
        adapter_specs=[AdapterCallSpec(adapter=TrafficAdapter(), kwargs={"radius_km": radius_km})]
    )
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))
