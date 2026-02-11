from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from backend.api.serializer import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService

snapshot_bp = Blueprint("snapshot", __name__)


@snapshot_bp.get("/snapshot")
def get_snapshot():
    """
    GET /snapshot?location=dublin&traffic_radius_km=1.0&tour_radius_km=5

    Returns a JSON-serialisable MobilitySnapshot.
    """
    location = request.args.get("location", "dublin")

    # Optional per-adapter params (passed via AdapterCallSpec)
    traffic_radius_km = request.args.get("traffic_radius_km", type=float)
    tour_radius_km = request.args.get("tour_radius_km", type=float)

    adapters = current_app.config["ADAPTERS"]  # dict name -> adapter instance

    specs = []

    # Bikes (no kwargs currently)
    specs.append(AdapterCallSpec(adapter=adapters["bikes"], kwargs={}))

    # Traffic
    traffic_kwargs = {}
    if traffic_radius_km is not None:
        traffic_kwargs["radius_km"] = traffic_radius_km
    specs.append(AdapterCallSpec(adapter=adapters["traffic"], kwargs=traffic_kwargs))

    # Air quality (no kwargs currently, you can add area later if you want)
    specs.append(AdapterCallSpec(adapter=adapters["airquality"], kwargs={}))

    # Tours
    tour_kwargs = {}
    if tour_radius_km is not None:
        tour_kwargs["radius_km"] = tour_radius_km
    specs.append(AdapterCallSpec(adapter=adapters["tours"], kwargs=tour_kwargs))

    service = SnapshotService(adapter_specs=specs)
    snapshot = service.build_snapshot(location=location)

    return jsonify(to_jsonable(snapshot))
