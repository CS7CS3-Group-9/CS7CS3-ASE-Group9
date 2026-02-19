"""
Frontend routing blueprint — thin proxy to the backend routing API.
All geocoding, Google routing, and optimisation logic lives in the backend.
"""
import requests
from flask import Blueprint, render_template, jsonify, request, current_app

routing_bp = Blueprint("routing", __name__, url_prefix="/routing")


@routing_bp.get("")
@routing_bp.get("/")
def routing():
    return render_template("dashboard/routing.html")


@routing_bp.get("/calculate")
def calculate():
    """Proxy the calculate request to the backend and return its response."""
    backend_url = current_app.config["BACKEND_API_URL"]
    try:
        # Use items(multi=True) so repeated params like stops[] and locked[]
        # are all forwarded — plain dict/ImmutableMultiDict drops duplicates.
        resp = requests.get(
            f"{backend_url}/routing/calculate",
            params=list(request.args.items(multi=True)),
            timeout=30,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.exceptions.Timeout:
        return jsonify({"error": "Routing service timed out. Please try again."}), 504
    except Exception as e:
        return jsonify({"error": f"Routing service unavailable: {e}"}), 502
