import os
from flask import Flask, redirect, url_for, request, session

from frontend.config import Config
from frontend.dashboard.overview import overview_bp
from frontend.dashboard.analytics import analytics_bp
from frontend.dashboard.recommendations import recommendations_bp
from frontend.dashboard.routing import routing_bp
from frontend.auth import auth_bp


def create_app(config_class=Config):
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config.from_object(config_class)

    app.register_blueprint(overview_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(recommendations_bp)
    app.register_blueprint(routing_bp)
    app.register_blueprint(auth_bp)

    @app.before_request
    def _require_login():
        endpoint = request.endpoint or ""
        if endpoint.startswith("static"):
            return None
        if endpoint in ("auth.login", "auth.login_post", "auth.logout"):
            return None
        if session.get("auth_ok"):
            return None
        next_url = request.full_path
        if next_url.endswith("?"):
            next_url = next_url[:-1]
        return redirect(url_for("auth.login", next=next_url))

    @app.route("/")
    def index():
        return redirect(url_for("overview.dashboard"))

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
