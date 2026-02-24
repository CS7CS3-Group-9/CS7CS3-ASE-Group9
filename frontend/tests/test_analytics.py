import pytest
from unittest.mock import patch, MagicMock

from frontend.app import create_app

SAMPLE_SNAPSHOT = {
    "timestamp": "2026-02-18T12:00:00+00:00",
    "bikes": {"available_bikes": 120, "available_docks": 80, "stations_reporting": 50},
    "traffic": {
        "congestion_level": "medium",
        "total_incidents": 5,
        "incidents_by_category": {"Jam": 3, "Road Closed": 2},
        "total_delay_minutes": 20,
        "average_speed": 30,
        "incidents": [],
    },
    "airquality": {
        "aqi_value": 45,
        "pollutants": {
            "pm2_5": 5.0,
            "pm10": 10.0,
            "nitrogen_dioxide": 15.0,
            "carbon_monoxide": 0.3,
            "ozone": 60.0,
            "sulphur_dioxide": 2.0,
        },
    },
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


def test_analytics_returns_200(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard/analytics")
    assert resp.status_code == 200


def test_analytics_uses_correct_template(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard/analytics")
    assert b"Analytics" in resp.data or b"airQualityChart" in resp.data


def test_analytics_data_endpoint(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard/analytics/data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "air_quality_chart" in data
    assert "bike_chart" in data
    assert "traffic_chart" in data


def test_analytics_chart_data_format(client):
    with patch("requests.get", return_value=_mock_resp(SAMPLE_SNAPSHOT)):
        resp = client.get("/dashboard/analytics/data")
    data = resp.get_json()
    for key in ("air_quality_chart", "bike_chart", "traffic_chart"):
        chart = data[key]
        assert "labels" in chart and isinstance(chart["labels"], list)
        assert "values" in chart and isinstance(chart["values"], list)
        assert len(chart["labels"]) == len(chart["values"])


def test_analytics_handles_empty_data(client):
    with patch("requests.get", return_value=_mock_resp(EMPTY_SNAPSHOT)):
        resp = client.get("/dashboard/analytics")
    assert resp.status_code == 200
