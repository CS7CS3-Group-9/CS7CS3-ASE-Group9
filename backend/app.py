from flask import Flask, jsonify
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone

from api.endpoints.example import example_bp
from backend.api.endpoints.snapshot import snapshot_bp
from backend.api.endpoints.bikes import bikes_bp
from backend.api.endpoints.traffic import traffic_bp
from backend.api.endpoints.airquality import airquality_bp
from backend.api.endpoints.tours import tours_bp


# command: python -m flask --app backend.app:create_app --debug run --port 5000
def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(bikes_bp)  # http://127.0.0.1:5000/bikes?location=dublin
    app.register_blueprint(traffic_bp)  # http://127.0.0.1:5000/traffic?location=dublin
    app.register_blueprint(airquality_bp)  # http://127.0.0.1:5000/airquality?location=dublin&lat=53.3498&lon=-6.2603
    app.register_blueprint(tours_bp)  # http://127.0.0.1:5000/tours?location=dublin&lat=53.3498&lon=-6.2603
    # app.register_blueprint(snapshot_bp) # http://127.0.0.1:5000/snapshot?location=dublin&lat=53.3498&lon=-6.2603
    return app


app = Flask(__name__)

# ── Register blueprints ──
app.register_blueprint(example_bp)

# ── Initialize Firebase (auto-discovers credentials on GKE) ──
try:
    firebase_admin.initialize_app()
    db = firestore.client()
    print("Firestore connected")
except Exception as e:
    db = None
    print(f"Firestore not available: {e}")


# ── Temporary test endpoint - remove after verifying Firestore ──
@app.route('/test-firestore')
def test_firestore():
    """Quick test to verify Firestore works from GKE."""
    if db is None:
        return jsonify({"status": "error", "message": "Firestore not initialized"}), 500

    try:
        # Write
        doc_ref = db.collection("test").document("gke-check")
        doc_ref.set({
            "status": "working",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Read back
        doc = doc_ref.get()
        data = doc.to_dict()

        # Clean up
        doc_ref.delete()

        return jsonify({
            "status": "ok",
            "firestore": "connected",
            "read_back": data,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ── Register more blueprints as you build them ──
# from api.endpoints.health import health_bp
# app.register_blueprint(health_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
    uvicorn.run(app, host="0.0.0.0", port=8080)
