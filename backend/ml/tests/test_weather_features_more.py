import os
from datetime import datetime, timezone

from backend.ml import weather_features as wf


def test_parse_timestamp_variants():
    assert wf._parse_timestamp("2026-03-01T12:00:00Z") is not None
    assert wf._parse_timestamp(str(1670000000.0)) is not None
    assert wf._parse_timestamp("") is None


def test_load_cache_and_nearest(tmp_path, monkeypatch):
    csvf = tmp_path / "weather.csv"
    # two records with different timestamps
    csvf.write_text("timestamp,rain\n2026-03-01T12:00:00Z,1.5\n2026-03-01T15:00:00Z,5.0\n")
    monkeypatch.setenv("WEATHER_FORECAST_PATH", str(csvf))
    now = datetime(2026, 3, 1, 13, 0, tzinfo=timezone.utc)
    features = wf.load_weather_features(now)
    # should pick the nearest (12:00 => rain 1.5)
    assert "weather_rain" in features


def test_auto_refresh_and_hours(monkeypatch):
    monkeypatch.setenv("WEATHER_AUTO_REFRESH", "false")
    assert not wf._auto_refresh_enabled()
    monkeypatch.setenv("WEATHER_AUTO_REFRESH", "true")
    assert wf._auto_refresh_enabled()
    monkeypatch.setenv("WEATHER_REFRESH_HOURS", "5")
    assert wf._refresh_hours() == 5
