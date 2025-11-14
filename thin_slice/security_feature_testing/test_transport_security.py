from flask import Flask, redirect, request

def test_http_redirect_to_https():
    app = Flask(__name__)

    @app.before_request
    def enforce_https():
        if request.scheme == "http":
            return redirect(request.url.replace("http://", "https://"), code=301)

    with app.test_client() as client:
        response = client.get("/", base_url="http://localhost")
        assert response.status_code == 301
        assert response.headers["Location"].startswith("https://")
