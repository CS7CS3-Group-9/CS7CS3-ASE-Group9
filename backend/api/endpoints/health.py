"""
GET /health endpoint.

Returns service status, configured adapters, and caching info.

Location: backend/api/endpoints/health.py
"""

from flask import Blueprint, jsonify
from datetime import datetime, timezone

health_bp = Blueprint("health", __name__)

# ── Registry of adapters in the system ──
# Maps adapter name -> full import path for the class
ADAPTER_REGISTRY = {
    "bikes": "backend.adapters.bikes_adapter.BikesAdapter",
    "routes": "backend.adapters.routes_adapter.RoutesAdapter",
    "traffic": "backend.adapters.traffic_adapter.TrafficAdapter",
    "air_quality": "backend.adapters.airquality_adapter.AirQualityAdapter",
    "tour": "backend.adapters.tour_adapter.TourAdapter",
}

# ── Placeholder for caching (update later when you add caching) ──
_last_snapshot_timestamp = None


def _check_adapter_status(adapter_path: str) -> str:
    """
    Check if an adapter class can be imported.

    Returns:
        'configured' if importable, 'unavailable' otherwise.
    """
    try:
        module_path, class_name = adapter_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        getattr(module, class_name)
        return "configured"
    except (ImportError, AttributeError):
        return "unavailable"


@health_bp.route("/health", methods=["GET"])
def health_check():
    """
    GET /health

    Returns JSON:
    {
        "status": "ok",
        "adapters": {
            "bikes": "configured",
            "routes": "configured",
            ...
        },
        "timestamp": "2026-02-10T12:00:00+00:00",
        "last_snapshot": null
    }
    """
    adapter_statuses = {}
    for name, path in ADAPTER_REGISTRY.items():
        adapter_statuses[name] = _check_adapter_status(path)

    return jsonify(
        {
            "status": "ok",
            "adapters": adapter_statuses,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_snapshot": _last_snapshot_timestamp,
        }
    )
