from flask import Flask
from backend.api.endpoints.bikes import bikes_bp
from backend.api.endpoints.traffic import traffic_bp
from backend.api.endpoints.airquality import airquality_bp
from backend.api.endpoints.tours import tours_bp


def create_app():
    app = Flask(__name__)
    app.register_blueprint(bikes_bp)
    app.register_blueprint(traffic_bp)
    app.register_blueprint(airquality_bp)
    app.register_blueprint(tours_bp)

    return app
