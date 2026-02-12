from __future__ import annotations

from flask import Flask

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
