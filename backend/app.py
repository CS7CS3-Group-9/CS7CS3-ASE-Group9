import os
from datetime import datetime, timezone

from flask import Flask, jsonify, current_app
import firebase_admin
from firebase_admin import firestore

from api.endpoints.example import example_bp
from api.endpoints.snapshot import snapshot_bp
from api.endpoints.bikes import bikes_bp
from api.endpoints.traffic import traffic_bp
from api.endpoints.airquality import airquality_bp
from api.endpoints.tours import tours_bp
from api.endpoints.health import health_bp


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

    app.register_blueprint(example_bp)
    app.register_blueprint(bikes_bp)
    app.register_blueprint(traffic_bp)
    app.register_blueprint(airquality_bp)
    app.register_blueprint(tours_bp)
    app.register_blueprint(snapshot_bp)
    app.register_blueprint(health_bp)

    _init_firestore(app)

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
