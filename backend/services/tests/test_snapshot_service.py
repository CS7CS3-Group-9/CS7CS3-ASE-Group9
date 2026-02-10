import pytest
from datetime import datetime

from backend.models.mobility_snapshot import MobilitySnapshot
from backend.services.snapshot_service import SnapshotService, AdapterCallSpec


# ----------------------------
# Dummy adapters for testing
# ----------------------------


class BikesAdapterOK:
    def source_name(self) -> str:
        return "bikes"

    def fetch(self, location: str = "dublin", **kwargs) -> MobilitySnapshot:
        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            bikes={"bikes": 123},  # could be BikeMetrics in your real code
        )


class TrafficAdapterOK:
    def source_name(self) -> str:
        return "traffic"

    def fetch(self, location: str = "dublin", **kwargs) -> MobilitySnapshot:
        # Adapter returns raw incidents list (as per your design)
        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            traffic=[{"incident": 1}, {"incident": 2}],  # stand-in for TrafficIncident objects
        )


class AirAdapterOK:
    def source_name(self) -> str:
        return "airquality"

    def fetch(self, location: str = "dublin", **kwargs) -> MobilitySnapshot:
        # Minimal object with a status attribute so SnapshotService can set it
        class DummyAir:
            def __init__(self):
                self.aqi_value = 80
                self.status = None

        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            airquality=DummyAir(),
        )


class AdapterFails:
    def source_name(self) -> str:
        return "fails"

    def fetch(self, location: str = "dublin", **kwargs) -> MobilitySnapshot:
        raise Exception("Simulated adapter failure")


class PartialNoneAdapter:
    def source_name(self) -> str:
        return "none"

    def fetch(self, location: str = "dublin", **kwargs) -> MobilitySnapshot:
        return MobilitySnapshot(timestamp=datetime.utcnow(), location=location, bikes=None)


# ----------------------------
# Tests
# ----------------------------


def test_build_snapshot_sets_location_and_timestamp():
    service = SnapshotService(adapters=[BikesAdapterOK()])
    snapshot = service.build_snapshot(location="dublin")

    assert snapshot.location == "dublin"
    assert isinstance(snapshot.timestamp, datetime)


def test_build_snapshot_merges_fields_from_multiple_adapters(monkeypatch):
    from backend.services import snapshot_service as ss_module

    monkeypatch.setattr(ss_module, "build_traffic_metrics", lambda incidents, radius_km: incidents)

    service = SnapshotService(adapters=[BikesAdapterOK(), TrafficAdapterOK()])
    snapshot = service.build_snapshot(location="dublin")

    assert snapshot.bikes == {"bikes": 123}
    assert isinstance(snapshot.traffic, list)
    assert len(snapshot.traffic) == 2


def test_source_status_live_for_successful_adapters(monkeypatch):
    from backend.services import snapshot_service as ss_module

    monkeypatch.setattr(ss_module, "build_traffic_metrics", lambda incidents, radius_km: incidents)

    service = SnapshotService(adapters=[BikesAdapterOK(), TrafficAdapterOK()])
    snapshot = service.build_snapshot(location="dublin")

    assert snapshot.source_status["bikes"] == "live"
    assert snapshot.source_status["traffic"] == "live"


def test_source_status_failed_when_adapter_raises():
    service = SnapshotService(adapters=[BikesAdapterOK(), AdapterFails()])
    snapshot = service.build_snapshot(location="dublin")

    assert snapshot.source_status["bikes"] == "live"
    assert snapshot.source_status["fails"] == "failed"


def test_service_continues_when_one_adapter_fails():
    service = SnapshotService(adapters=[AdapterFails(), BikesAdapterOK()])
    snapshot = service.build_snapshot(location="dublin")

    # Still gets bikes even though first adapter failed
    assert snapshot.bikes == {"bikes": 123}
    assert snapshot.source_status["fails"] == "failed"
    assert snapshot.source_status["bikes"] == "live"


def test_traffic_analytics_is_applied(monkeypatch):
    """
    SnapshotService should convert traffic list -> TrafficMetrics by calling build_traffic_metrics.
    We monkeypatch it to confirm it was called and that output replaces list.
    """
    from backend.services import snapshot_service as ss_module

    sentinel_metrics = object()

    def fake_build_traffic_metrics(incidents, radius_km: float):
        assert isinstance(incidents, list)
        assert radius_km == 1.0  # matches SnapshotService default in your implementation
        return sentinel_metrics

    monkeypatch.setattr(ss_module, "build_traffic_metrics", fake_build_traffic_metrics)

    service = SnapshotService(adapters=[TrafficAdapterOK()])
    snapshot = service.build_snapshot(location="dublin")

    assert snapshot.traffic is sentinel_metrics


def test_airquality_status_is_set_by_analytics(monkeypatch):
    """
    SnapshotService should compute overall air quality level and set airquality.status
    if the model has that attribute.
    """
    from backend.services import snapshot_service as ss_module

    def fake_overall_air_quality_level(air_model):
        return "medium"

    monkeypatch.setattr(ss_module, "overall_air_quality_level", fake_overall_air_quality_level)

    service = SnapshotService(adapters=[AirAdapterOK()])
    snapshot = service.build_snapshot(location="dublin")

    assert snapshot.airquality is not None
    assert snapshot.airquality.status == "medium"


def test_init_rejects_both_adapters_and_specs():
    with pytest.raises(ValueError):
        SnapshotService(
            adapters=[BikesAdapterOK()],
            adapter_specs=[AdapterCallSpec(adapter=BikesAdapterOK(), kwargs={})],
        )


def test_init_requires_at_least_one_adapter():
    with pytest.raises(ValueError):
        SnapshotService()


def test_adapter_specs_pass_kwargs_to_adapter(monkeypatch):
    """
    Ensures SnapshotService can call adapters with per-adapter kwargs (no hardcoding).
    """
    from backend.services import snapshot_service as ss_module

    monkeypatch.setattr(ss_module, "build_traffic_metrics", lambda incidents, radius_km: incidents)

    class AdapterWithKwargs:
        def source_name(self) -> str:
            return "kw"

        def fetch(self, location: str = "dublin", radius_km: float = 0.0) -> MobilitySnapshot:
            return MobilitySnapshot(
                timestamp=datetime.utcnow(),
                location=location,
                traffic=[{"radius_km": radius_km}],
            )

    service = SnapshotService(adapter_specs=[AdapterCallSpec(adapter=AdapterWithKwargs(), kwargs={"radius_km": 7.5})])
    snapshot = service.build_snapshot(location="dublin")

    assert snapshot.source_status["kw"] == "live"
    assert snapshot.traffic[0]["radius_km"] == 7.5


def test_merge_does_not_overwrite_with_none():
    service = SnapshotService(adapters=[BikesAdapterOK(), PartialNoneAdapter()])
    snapshot = service.build_snapshot("dublin")
    assert snapshot.bikes == {"bikes": 123}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
