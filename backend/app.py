# app entry point - Flask

from flask import Flask, jsonify
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone

from api.endpoints.example import example_bp

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