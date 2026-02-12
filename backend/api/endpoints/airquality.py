from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.airquality_location_adapter import AirQualityLocationAdapter

airquality_bp = Blueprint("airquality", __name__)


@airquality_bp.get("/airquality")
def get_airquality():
    location = request.args.get("location", "dublin")

    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if lat is None or lon is None:
        return jsonify({"error": "Provide lat and lon, e.g. /airquality?lat=53.3498&lon=-6.2603"}), 400

    try:
        latitude = float(lat)
        longitude = float(lon)
    except ValueError:
        return jsonify({"error": "lat and lon must be numbers"}), 400

    service = SnapshotService(
        adapter_specs=[
            AdapterCallSpec(
                adapter=AirQualityLocationAdapter(),
                kwargs={"latitude": latitude, "longitude": longitude},
            )
        ]
    )
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))
