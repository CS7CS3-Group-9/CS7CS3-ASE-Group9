from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app import create_app
from backend.models.mobility_snapshot import MobilitySnapshot


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_traffic_endpoint_success(monkeypatch, client):
    from backend.services import snapshot_service as ss_module

    def fake_build_snapshot(self, location="dublin"):
        # return already-analytics’d traffic or raw traffic — endpoint tests
        # only care that route returns JSON correctly.
        return MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location=location,
            traffic={"congestion_level": "high", "total_incidents": 3},
            source_status={"traffic": "live"},
        )

    monkeypatch.setattr(ss_module.SnapshotService, "build_snapshot", fake_build_snapshot)

    resp = client.get("/traffic?location=dublin&radius_km=5")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["location"] == "dublin"
    assert data["traffic"]["congestion_level"] == "high"
    assert data["source_status"]["traffic"] == "live"


def test_traffic_endpoint_radius_km_bad_value_still_works(monkeypatch, client):
    from backend.services import snapshot_service as ss_module

    def fake_build_snapshot(self, location="dublin"):
        return MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location=location,
            traffic={"ok": True},
            source_status={"traffic": "live"},
        )

    monkeypatch.setattr(ss_module.SnapshotService, "build_snapshot", fake_build_snapshot)

    # radius_km is invalid -> endpoint should fall back to default, still 200
    resp = client.get("/traffic?location=dublin&radius_km=not-a-number")
    assert resp.status_code == 200
