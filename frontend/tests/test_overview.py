import pytest
from unittest.mock import patch, MagicMock

from frontend.app import create_app

SAMPLE_SNAPSHOT = {
    "timestamp": "2026-02-18T12:00:00+00:00",
    "bikes": {"available_bikes": 120, "available_docks": 80, "stations_reporting": 50},
    "traffic": {
        "congestion_level": "low",
        "total_incidents": 2,
        "incidents_by_category": {"Jam": 2},
        "incidents_by_severity": {"Minor": 2},
        "total_delay_minutes": 10,
        "average_delay_minutes": 5,
        "average_speed": 50,
        "incidents": [],
    },
    "airquality": {
        "aqi_value": 45,
        "pollutants": {
            "pm2_5": 5.0, "pm10": 10.0, "nitrogen_dioxide": 15.0,
            "carbon_monoxide": 0.3, "ozone": 60.0, "sulphur_dioxide": 2.0,
        },
    },
    "tours": {"total_attractions": 5, "attractions": []},
    "source_status": {"bikes": "live", "traffic": "live", "airquality": "live"},
}

CITYBIKES_RESPONSE = {
    "network": {
        "stations": [{
            "name": "Test Station",
            "latitude": 53.34,
            "longitude": -6.26,
            "free_bikes": 5,
            "empty_slots": 10,
            "extra": {"slots": 15},
        }]
    }
}


def _mock_resp(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["BACKEND_API_URL"] = "http://mock-backend"
    with app.test_client() as c:
        yield c


def test_overview_returns_200(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard")
    assert resp.status_code == 200


def test_overview_uses_correct_template(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard")
    assert b"Dublin City" in resp.data or b"dashboard" in resp.data.lower()


def test_overview_contains_indicators(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard")
    # 120 available bikes should appear in the rendered HTML
    assert b"120" in resp.data


def test_overview_contains_map_data(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard")
    assert b"map" in resp.data.lower()


def test_overview_data_endpoint(client):
    with patch("requests.get", side_effect=[
        _mock_resp(SAMPLE_SNAPSHOT),
        _mock_resp(CITYBIKES_RESPONSE),
    ]):
        resp = client.get("/dashboard/data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "bikes" in data
    assert "traffic" in data
    assert "airquality" in data
    assert "bike_stations" in data


def test_overview_handles_backend_failure(client):
    with patch("requests.get", side_effect=ConnectionError("backend down")):
        resp = client.get("/dashboard")
    # Must still return 200 with a degraded / empty state
    assert resp.status_code == 200
