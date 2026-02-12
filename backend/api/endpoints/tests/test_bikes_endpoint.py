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


def test_bikes_endpoint_success(monkeypatch, client):
    from backend.services import snapshot_service as ss_module

    def fake_build_snapshot(self, location="dublin"):
        return MobilitySnapshot(
            timestamp=datetime.now(timezone.utc),
            location=location,
            bikes={"available_bikes": 10},
            source_status={"bikes": "live"},
        )

    monkeypatch.setattr(ss_module.SnapshotService, "build_snapshot", fake_build_snapshot)

    resp = client.get("/bikes?location=dublin")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["location"] == "dublin"
    assert data["bikes"]["available_bikes"] == 10
    assert data["source_status"]["bikes"] == "live"
