from datetime import datetime, timedelta, timezone

from fallback.predictor import predict_snapshot, predict_value
from models.mobility_snapshot import MobilitySnapshot


def _make_snapshot(age_seconds: int = 0):
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return MobilitySnapshot(
        timestamp=ts,
        location="dublin",
        bikes={"available_bikes": 10},
        source_status={"bikes": "live"},
    )


def test_predict_snapshot_none_input():
    assert predict_snapshot(None) is None


def test_predict_snapshot_too_old_returns_none():
    snap = _make_snapshot(age_seconds=1200)
    assert predict_snapshot(snap, max_age_seconds=600) is None


def test_predict_snapshot_updates_timestamp_and_status():
    snap = _make_snapshot(age_seconds=60)
    result = predict_snapshot(snap, max_age_seconds=600)
    assert result is not None
    assert result.snapshot.timestamp != snap.timestamp
    assert result.snapshot.source_status["bikes"] == "predicted"
    assert 0.0 <= result.confidence <= 1.0
    assert result.based_on == snap.timestamp


def test_predict_value():
    assert predict_value(None) is None
    assert predict_value(10, drift=1.5) == 11.5
