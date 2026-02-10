from __future__ import annotations

from flask import Flask

from backend.api.endpoints.snapshot import snapshot_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(snapshot_bp)
    return app
