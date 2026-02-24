import pytest
from unittest.mock import patch, MagicMock

from frontend.app import create_app

HIGH_TRAFFIC_SNAPSHOT = {
    "timestamp": "2026-02-18T12:00:00+00:00",
    "bikes": {"available_bikes": 5, "available_docks": 100, "stations_reporting": 50},
    "traffic": {
        "congestion_level": "high",
        "total_incidents": 15,
        "incidents_by_category": {"Jam": 15},
        "total_delay_minutes": 60,
        "average_speed": 15,
        "incidents": [],
    },
    "airquality": {"aqi_value": 120, "pollutants": {}},
    "source_status": {},
}

EMPTY_SNAPSHOT = {"bikes": None, "traffic": None, "airquality": None, "source_status": {}}


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


def test_recommendations_returns_200(client):
    with patch("requests.get", return_value=_mock_resp(HIGH_TRAFFIC_SNAPSHOT)):
        resp = client.get("/dashboard/recommendations")
    assert resp.status_code == 200


def test_recommendations_uses_correct_template(client):
    with patch("requests.get", return_value=_mock_resp(HIGH_TRAFFIC_SNAPSHOT)):
        resp = client.get("/dashboard/recommendations")
    assert b"Recommendations" in resp.data


def test_recommendations_data_is_list(client):
    with patch("requests.get", return_value=_mock_resp(HIGH_TRAFFIC_SNAPSHOT)):
        resp = client.get("/dashboard/recommendations")
    # With high congestion + low bikes + poor AQI, cards should be rendered
    assert resp.status_code == 200
    assert b"priority-high" in resp.data


def test_recommendation_has_required_fields(client):
    with patch("requests.get", return_value=_mock_resp(HIGH_TRAFFIC_SNAPSHOT)):
        resp = client.get("/dashboard/recommendations")
    html = resp.data.decode()
    # Each card must show title, description, priority badge, source badge
    assert "priority-badge" in html
    assert "source-badge" in html
    assert "rec-desc" in html


def test_recommendations_handles_empty_list(client):
    with patch("requests.get", return_value=_mock_resp(EMPTY_SNAPSHOT)):
        resp = client.get("/dashboard/recommendations")
    assert resp.status_code == 200
    # The "All Clear" fallback recommendation is rendered
    assert b"All Clear" in resp.data or b"No recommendations" in resp.data


def test_recommendations_handles_backend_failure(client):
    with patch("requests.get", side_effect=ConnectionError("backend down")):
        resp = client.get("/dashboard/recommendations")
    assert resp.status_code == 200
    # Error banner shown but page still renders
    assert b"backend" in resp.data.lower() or b"unavailable" in resp.data.lower()
