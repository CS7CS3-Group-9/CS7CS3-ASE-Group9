from flask import Blueprint, render_template, current_app
from .overview import _fetch_snapshot, _build_recommendations

recommendations_bp = Blueprint("recommendations", __name__, url_prefix="/dashboard/recommendations")


@recommendations_bp.get("")
@recommendations_bp.get("/")
def recommendations():
    backend_url = current_app.config["BACKEND_API_URL"]
    snapshot, error = _fetch_snapshot(backend_url)
    recs = _build_recommendations(
        snapshot.get("bikes"),
        snapshot.get("traffic"),
        snapshot.get("airquality"),
    )
    return render_template(
        "dashboard/recommendations.html",
        recommendations=recs,
        timestamp=snapshot.get("timestamp"),
        backend_error=error,
    )
