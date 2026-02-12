from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.bikes_adapter import BikesAdapter

bikes_bp = Blueprint("bikes", __name__)


@bikes_bp.get("/bikes")
def get_bikes():
    location = request.args.get("location", "dublin")

    service = SnapshotService(adapter_specs=[AdapterCallSpec(adapter=BikesAdapter(), kwargs={})])
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))
