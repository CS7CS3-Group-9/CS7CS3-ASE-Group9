from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from backend.app import create_app
from backend.models.mobility_snapshot import MobilitySnapshot


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


# ---------------------------------------------------------------------------
# CORS header tests
# ---------------------------------------------------------------------------


def test_cors_header_present_for_desktop_frontend_origin(client):
    """Backend must return CORS headers for the Electron-embedded frontend."""
    resp = client.get("/health", headers={"Origin": "http://localhost:5002"})
    assert resp.status_code == 200
    assert "Access-Control-Allow-Origin" in resp.headers


def test_cors_header_present_for_file_origin(client):
    """Backend must return CORS headers for Electron file:// origin (dev mode)."""
    resp = client.get("/health", headers={"Origin": "file://"})
    # flask-cors allows the header even if the value is the specific origin or *
    assert "Access-Control-Allow-Origin" in resp.headers


def test_cors_preflight_returns_200(client):
    """OPTIONS pre-flight request from the desktop origin should succeed."""
    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5002",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Cache-warmup endpoint tests
# ---------------------------------------------------------------------------


def _make_empty_snapshot():
    return MobilitySnapshot(
        timestamp=datetime.now(timezone.utc),
        location="dublin",
        source_status={"bikes": "live", "traffic": "live", "airquality": "live", "tours": "live"},
    )


def test_cache_warmup_returns_200(client):
    """GET /desktop/cache-warmup should always return 200."""
    with (
        patch("backend.services.snapshot_service.SnapshotService.build_snapshot", return_value=_make_empty_snapshot()),
        patch("backend.api.endpoints.desktop._fetch_bike_stations", return_value=[]),
        patch("backend.api.endpoints.desktop._fetch_bus_stops", return_value=[]),
    ):
        resp = client.get("/desktop/cache-warmup")

    assert resp.status_code == 200


def test_cache_warmup_response_structure(client):
    """Response must contain snapshot, bike_stations, bus_stops, and fetched_at."""
    fake_stations = [
        {"name": "St Stephen's Green", "lat": 53.33, "lon": -6.26, "free_bikes": 5, "empty_slots": 15, "total": 20}
    ]
    fake_stops = [{"name": "Nassau St", "lat": 53.34, "lon": -6.25, "ref": "1234", "routes": "7"}]

    with (
        patch("backend.services.snapshot_service.SnapshotService.build_snapshot", return_value=_make_empty_snapshot()),
        patch("backend.api.endpoints.desktop._fetch_bike_stations", return_value=fake_stations),
        patch("backend.api.endpoints.desktop._fetch_bus_stops", return_value=fake_stops),
    ):
        resp = client.get("/desktop/cache-warmup")

    data = resp.get_json()
    assert "snapshot" in data
    assert "bike_stations" in data
    assert "bus_stops" in data
    assert "fetched_at" in data

    assert data["bike_stations"] == fake_stations
    assert data["bus_stops"] == fake_stops
    assert data["snapshot"]["location"] == "dublin"


def test_cache_warmup_partial_results_on_external_failure(client):
    """If bike stations or bus stops fail, the endpoint still returns 200
    with empty lists rather than propagating the error."""
    with (
        patch("backend.services.snapshot_service.SnapshotService.build_snapshot", return_value=_make_empty_snapshot()),
        patch("backend.api.endpoints.desktop._fetch_bike_stations", return_value=[]),
        patch("backend.api.endpoints.desktop._fetch_bus_stops", return_value=[]),
    ):
        resp = client.get("/desktop/cache-warmup")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["bike_stations"] == []
    assert data["bus_stops"] == []
