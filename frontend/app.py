import os
from flask import Flask, redirect, url_for

from frontend.config import Config
from frontend.dashboard.overview import overview_bp
from frontend.dashboard.analytics import analytics_bp
from frontend.dashboard.recommendations import recommendations_bp


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

    @app.route("/")
    def index():
        return redirect(url_for("overview.dashboard"))

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
