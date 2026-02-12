from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.tour_adapter import TourAdapter

tours_bp = Blueprint("tours", __name__)


@tours_bp.get("/tours")
def get_tours():
    location = request.args.get("location", "dublin")

    try:
        radius_km = float(request.args.get("radius_km", "1.0"))
    except ValueError:
        radius_km = 1.0
    radius_km = max(0.1, min(radius_km, 50.0))

    service = SnapshotService(adapter_specs=[AdapterCallSpec(adapter=TourAdapter(), kwargs={"radius_km": radius_km})])
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))
