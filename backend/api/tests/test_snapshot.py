import pytest
from datetime import datetime, timezone
from flask import Flask

from backend.models.mobility_snapshot import MobilitySnapshot
from backend.api.endpoints.snapshot import snapshot_bp
from backend.models.traffic_models import TrafficIncident


class DummyAdapter:
    def __init__(self, name, partial):
        self._name = name
        self._partial = partial

    def source_name(self):
        return self._name

    def fetch(self, location="dublin", **kwargs):
        return self._partial(location, **kwargs)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(snapshot_bp)

    # Dummy adapters (no external calls)
    app.config["ADAPTERS"] = {
        "bikes": DummyAdapter(
            "bikes",
            lambda location, **kw: MobilitySnapshot(
                timestamp=datetime.now(timezone.utc),
                location=location,
                bikes={"available": 10},
            ),
        ),
        "traffic": DummyAdapter(
            "traffic",
            lambda location, **kw: MobilitySnapshot(
                timestamp=datetime.now(timezone.utc),
                location=location,
                traffic=[
                    TrafficIncident(
                        category="Jam",
                        severity="Major",
                        description="Stationary traffic",
                        from_location="A",
                        to_location="B",
                        road="R123",
                        length_meters=100.0,
                        delay_seconds=60,
                        delay_minutes=1.0,
                    )
                ],
            ),
        ),
        "airquality": DummyAdapter(
            "airquality",
            lambda location, **kw: MobilitySnapshot(
                timestamp=datetime.now(timezone.utc),
                location=location,
                airquality={"aqi_value": 55},
            ),
        ),
        "tours": DummyAdapter(
            "tours",
            lambda location, **kw: MobilitySnapshot(
                timestamp=datetime.now(timezone.utc),
                location=location,
                tours={"total_attractions": 3},
            ),
        ),
    }

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_snapshot_returns_200(client):
    r = client.get("/snapshot")
    assert r.status_code == 200


def test_snapshot_returns_json(client):
    r = client.get("/snapshot")
    assert r.mimetype == "application/json"


def test_snapshot_contains_expected_keys(client):
    r = client.get("/snapshot?location=dublin")
    data = r.get_json()

    assert data["location"] == "dublin"
    assert "timestamp" in data
    assert "source_status" in data

    # merged fields
    assert data["bikes"] == {"available": 10}
    assert data["traffic"]["total_incidents"] == 1
    assert data["traffic"]["incidents_by_category"]["Jam"] == 1
    assert data["airquality"] == {"aqi_value": 55}
    assert data["tours"] == {"total_attractions": 3}


def test_snapshot_accepts_location_param(client):
    r = client.get("/snapshot?location=malahide")
    data = r.get_json()
    assert data["location"] == "malahide"
