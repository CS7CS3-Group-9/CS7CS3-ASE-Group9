import os
from datetime import datetime, timezone

from flask import Flask, jsonify, current_app
from flask_cors import CORS
import firebase_admin
from firebase_admin import firestore

from backend.api.endpoints.example import example_bp
from backend.api.endpoints.snapshot import snapshot_bp
from backend.api.endpoints.bikes import bikes_bp
from backend.api.endpoints.traffic import traffic_bp
from backend.api.endpoints.airquality import airquality_bp
from backend.api.endpoints.tours import tours_bp
from backend.api.endpoints.health import health_bp
from backend.api.endpoints.routing import routing_api_bp
from backend.api.endpoints.buses import buses_bp
from backend.api.endpoints.desktop import desktop_bp
from backend.ml.weather_features import refresh_weather_if_needed


def _init_firestore(app: Flask) -> None:
    enable = os.getenv("ENABLE_FIRESTORE", "").lower() in ("1", "true", "yes")
    if not enable:
        app.config["FIRESTORE_DB"] = None
        return

    try:
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app()
        app.config["FIRESTORE_DB"] = firestore.client()
    except Exception:
        app.config["FIRESTORE_DB"] = None


def _get_firestore_db():
    return current_app.config.get("FIRESTORE_DB")


# command: python -m flask --app backend.app:create_app --debug run --port 5000
def create_app() -> Flask:
    app = Flask(__name__)

    # CORS for desktop app: Electron renderer runs at http://localhost:5002
    # and may also make direct requests from file:// in development.
    # The web frontend communicates via server-side Python requests (not browser
    # fetch), so these headers have no effect on it.
    CORS(
        app,
        origins=[
            "http://localhost:5002",
            "http://localhost:5001",
            "file://",
            "app://.",
        ],
    )

    app.register_blueprint(example_bp)
    app.register_blueprint(bikes_bp)
    app.register_blueprint(traffic_bp)
    app.register_blueprint(airquality_bp)
    app.register_blueprint(tours_bp)
    app.register_blueprint(snapshot_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(routing_api_bp)
    app.register_blueprint(buses_bp)
    app.register_blueprint(desktop_bp)

    _init_firestore(app)
    try:
        refresh_weather_if_needed()
    except Exception:
        pass

    @app.route("/test-firestore")
    def test_firestore():
        """Quick test to verify Firestore works from the runtime environment."""
        db = _get_firestore_db()
        if db is None:
            return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

        try:
            doc_ref = db.collection("test").document("gke-check")
            doc_ref.set(
                {
                    "status": "working",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            doc = doc_ref.get()
            data = doc.to_dict()
            doc_ref.delete()

            return jsonify(
                {
                    "status": "ok",
                    "firestore": "connected",
                    "read_back": data,
                }
            )
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
