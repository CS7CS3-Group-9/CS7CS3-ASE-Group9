from flask import Flask

from backend.api.deps import build_adapters
from backend.api.endpoints.health import health_bp
from backend.api.endpoints.snapshot import snapshot_bp


def create_app():
    app = Flask(__name__)

    # Register adapters once at startup
    app.config["ADAPTERS"] = build_adapters()

    # Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(snapshot_bp)

    return app
