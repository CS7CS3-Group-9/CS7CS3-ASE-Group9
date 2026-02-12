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


def test_tours_endpoint_success(monkeypatch, client):
    from backend.services import snapshot_service as ss_module

    def fake_build_snapshot(self, location="dublin"):
        return MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location=location,
            tours=[{"name": "Tour A"}, {"name": "Tour B"}],
            source_status={"tours": "live"},
        )

    monkeypatch.setattr(ss_module.SnapshotService, "build_snapshot", fake_build_snapshot)

    resp = client.get("/tours?location=dublin&radius_km=10")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["location"] == "dublin"
    assert isinstance(data["tours"], list)
    assert len(data["tours"]) == 2
    assert data["source_status"]["tours"] == "live"
