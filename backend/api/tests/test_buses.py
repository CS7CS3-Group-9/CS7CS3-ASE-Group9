import time
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from backend.api.endpoints import buses as buses_module


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(buses_module, "_GTFS_STOPS_CACHE", None)
    monkeypatch.setattr(buses_module, "_GTFS_STOP_IDS_CACHE", None)
    monkeypatch.setattr(buses_module, "_ARRIVALS_CACHE", {})
    monkeypatch.setattr(buses_module, "_ARRIVALS_CACHE_TS", None)
    monkeypatch.setattr(buses_module, "_STOPS_CACHE", {})
    monkeypatch.setattr(buses_module, "_GTFS_ROOT", tmp_path)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(buses_module.buses_bp)
    return app.test_client()


def _mock_response(data):
    response = MagicMock()
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response


def test_bus_stops_gtfs_mode_returns_enriched_stops(client, monkeypatch, tmp_path):
    gtfs_dir = tmp_path / "GTFS"
    gtfs_dir.mkdir()
    (gtfs_dir / "stops.txt").write_text("stop_id,stop_name,stop_lat,stop_lon\n", encoding="utf-8")

    monkeypatch.setattr(
        buses_module,
        "_load_gtfs_stops",
        lambda: (
            [{"stop_id": "S1", "name": "Stop 1", "lat": 53.34, "lon": -6.26, "ref": "S1", "routes": ""}],
            {"S1"},
        ),
    )
    monkeypatch.setattr(buses_module, "_get_arrivals_next_hour", lambda stop_ids: {"S1": 4})

    with patch("backend.api.endpoints.buses.requests.post") as mock_post:
        resp = client.get("/buses/stops")

    assert resp.status_code == 200
    assert resp.get_json() == [
        {
            "arrivals_next_hour": 4,
            "lat": 53.34,
            "lon": -6.26,
            "name": "Stop 1",
            "ref": "S1",
            "routes": "",
            "stop_id": "S1",
        }
    ]
    mock_post.assert_not_called()


def test_bus_stops_gtfs_error_returns_502(client, monkeypatch, tmp_path):
    gtfs_dir = tmp_path / "GTFS"
    gtfs_dir.mkdir()
    (gtfs_dir / "stops.txt").write_text("stop_id,stop_name,stop_lat,stop_lon\n", encoding="utf-8")

    monkeypatch.setattr(
        buses_module,
        "_load_gtfs_stops",
        MagicMock(side_effect=RuntimeError("gtfs exploded")),
    )

    resp = client.get("/buses/stops")

    assert resp.status_code == 502
    assert "gtfs exploded" in resp.get_json()["error"]


def test_bus_stops_overpass_success_parses_response_and_sets_cache_headers(client):
    payload = {
        "elements": [
            {"lat": 53.3401, "lon": -6.2601, "tags": {"name": "Main Stop", "ref": "123", "route_ref": "15,16"}},
            {"tags": {"name": "Incomplete Stop"}},
        ]
    }

    with patch(
        "backend.api.endpoints.buses.requests.post",
        return_value=_mock_response(payload),
    ) as mock_post:
        resp = client.get("/buses/stops?radius_km=1.5&lat=53.35&lon=-6.27")

    assert resp.status_code == 200
    assert resp.get_json() == [{"name": "Main Stop", "lat": 53.3401, "lon": -6.2601, "ref": "123", "routes": "15,16"}]
    assert resp.headers["Cache-Control"] == "public, max-age=600"
    assert "around:1500,53.35,-6.27" in mock_post.call_args.kwargs["data"]


def test_bus_stops_uses_fresh_in_memory_cache_for_repeat_requests(client):
    payload = {"elements": [{"lat": 53.3401, "lon": -6.2601, "tags": {"name": "Cached Stop", "ref": "123"}}]}

    with patch(
        "backend.api.endpoints.buses.requests.post",
        return_value=_mock_response(payload),
    ) as mock_post:
        first = client.get("/buses/stops?radius_km=2")
        second = client.get("/buses/stops?radius_km=2")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json() == second.get_json()
    assert mock_post.call_count == 1


def test_bus_stops_returns_stale_cache_when_overpass_fails(client):
    cache_key = buses_module._cache_key(None, buses_module._DUBLIN_LAT, buses_module._DUBLIN_LON)
    buses_module._STOPS_CACHE[cache_key] = {
        "data": [{"name": "Stale Stop", "lat": 53.34, "lon": -6.26, "ref": "", "routes": ""}],
        "timestamp": time.time() - (buses_module._CACHE_TTL_SECONDS + 1),
    }

    with patch(
        "backend.api.endpoints.buses.requests.post",
        side_effect=RuntimeError("overpass down"),
    ):
        resp = client.get("/buses/stops")

    assert resp.status_code == 200
    assert resp.headers["X-Cache"] == "stale"
    assert resp.headers["Cache-Control"] == "public, max-age=60"
    assert resp.get_json()[0]["name"] == "Stale Stop"


def test_bus_stops_invalid_params_fall_back_to_default_query_values(client):
    with patch(
        "backend.api.endpoints.buses.requests.post",
        return_value=_mock_response({"elements": []}),
    ) as mock_post:
        resp = client.get("/buses/stops?radius_km=not-a-number&lat=oops&lon=nope")

    assert resp.status_code == 200
    assert resp.get_json() == []
    assert "around:5000,53.3498,-6.2603" in mock_post.call_args.kwargs["data"]
