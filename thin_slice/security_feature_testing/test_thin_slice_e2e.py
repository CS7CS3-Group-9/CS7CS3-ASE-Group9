import pytest
from unittest.mock import MagicMock
from flask import Flask, jsonify
import requests
import redis


def create_app():
    app = Flask(__name__)
    app.secret_key = "testing"

    @app.route("/data/weather")
    def weather_data():
        token = requests.get("https://firebase.validate.token.mock").text
        if token != "VALID":
            return jsonify({"error": "Unauthorized"}), 401

        r = redis.Redis()
        cached = r.get("weather")
        if cached:
            # Support both bytes and str
            value = cached.decode() if isinstance(cached, bytes) else cached
            return jsonify({"source": "cache", "data": value})

        # Fetch external API
        data = requests.get("https://api.externalweather.mock").text
        r.setex("weather", 60, data)
        return jsonify({"source": "api", "data": data})

    return app


def test_thin_slice_e2e_flow(monkeypatch):
    app = create_app()

    # Mock Firebase and external API
    def mock_requests_get(url, *args, **kwargs):
        if "firebase" in url:
            m = MagicMock()
            m.text = "VALID"
            return m
        else:
            m = MagicMock()
            m.text = "SUNNY"
            return m

    monkeypatch.setattr(requests, "get", mock_requests_get)

    # Mock Redis
    fake_redis = {}

    class FakeRedis:
        def get(self, k):
            value = fake_redis.get(k)
            return value.encode() if isinstance(value, str) else value

        def setex(self, k, ttl, v):
            fake_redis[k] = v

    monkeypatch.setattr(redis, "Redis", lambda *a, **kw: FakeRedis())

    with app.test_client() as c:
        # First request (API)
        response = c.get("/data/weather")
        json_data = response.get_json()
        assert response.status_code == 200
        assert json_data["source"] == "api"
        assert json_data["data"] == "SUNNY"

        # Second request (cache)
        response2 = c.get("/data/weather")
        json_data2 = response2.get_json()
        assert json_data2["source"] == "cache"
        assert json_data2["data"] == "SUNNY"
