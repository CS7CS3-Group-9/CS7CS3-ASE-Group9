from __future__ import annotations

from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService

from backend.adapters.bikes_adapter import BikesAdapter
from backend.adapters.traffic_adapter import TrafficAdapter
from backend.adapters.airquality_adapter import AirQualityAdapter
from backend.adapters.tour_adapter import TourAdapter
from backend.adapters.airquality_location_adapter import AirQualityLocationAdapter

snapshot_bp = Blueprint("snapshot", __name__)


def build_adapter_specs(
    include: list[str],
    radius_km: float,
    latitude: float | None,
    longitude: float | None,
) -> list[AdapterCallSpec]:
    specs: list[AdapterCallSpec] = []

    if "bikes" in include:
        specs.append(AdapterCallSpec(adapter=BikesAdapter(), kwargs={}))

    if "traffic" in include:
        specs.append(AdapterCallSpec(adapter=TrafficAdapter(), kwargs={"radius_km": radius_km}))

    if "airquality" in include:
        specs.append(
            AdapterCallSpec(
                adapter=AirQualityLocationAdapter(),
                kwargs={"latitude": latitude, "longitude": longitude},
            )
        )

    if "tours" in include:
        specs.append(AdapterCallSpec(adapter=TourAdapter(), kwargs={"radius_km": radius_km}))

    return specs


@snapshot_bp.get("/snapshot")
def get_snapshot():
    location = request.args.get("location", "dublin")

    try:
        radius_km = float(request.args.get("radius_km", "1.0"))
    except ValueError:
        radius_km = 1.0
    radius_km = max(0.1, min(radius_km, 50.0))

    lat_raw = request.args.get("lat")
    lon_raw = request.args.get("lon")
    latitude = None
    longitude = None
    try:
        if lat_raw is not None and lon_raw is not None:
            latitude = float(lat_raw)
            longitude = float(lon_raw)
    except ValueError:
        latitude = None
        longitude = None

    include = request.args.getlist("include")
    if not include:
        include = ["bikes", "traffic", "airquality", "tours"]

    adapter_specs = build_adapter_specs(include, radius_km, latitude, longitude)
    service = SnapshotService(adapter_specs=adapter_specs)
    snapshot = service.build_snapshot(location=location)

    return jsonify(to_jsonable(snapshot))
