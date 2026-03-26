import os
from datetime import datetime, timezone
from pathlib import Path

from backend.ml import weather_features as wf


def test_parse_timestamp_formats():
    ts = wf._parse_timestamp("2020-01-01T00:00:00Z")
    assert ts is not None and ts.tzinfo is not None
    ts2 = wf._parse_timestamp("0")
    assert ts2 == datetime.fromtimestamp(0, tz=timezone.utc)
    assert wf._parse_timestamp("") is None
    assert wf._parse_timestamp(None) is None
    assert wf._parse_timestamp("not a date") is None


def test_parse_float_and_nearest_record_and_refresh_env():
    assert wf._parse_float(None) is None
    assert wf._parse_float("") is None
    assert wf._parse_float("1.23") == 1.23

    records = [
        (datetime.fromtimestamp(0, tz=timezone.utc), {"a": 1}),
        (datetime.fromtimestamp(1000, tz=timezone.utc), {"a": 2}),
    ]
    nearest = wf._nearest_record(records, datetime.fromtimestamp(10, tz=timezone.utc))
    assert nearest[1]["a"] == 1

    # env toggles
    os.environ["WEATHER_AUTO_REFRESH"] = "false"
    assert not wf._auto_refresh_enabled()
    os.environ["WEATHER_AUTO_REFRESH"] = "true"
    assert wf._auto_refresh_enabled()

    os.environ["WEATHER_REFRESH_HOURS"] = "bad"
    assert wf._refresh_hours() == 24
    os.environ["WEATHER_REFRESH_HOURS"] = "2"
    assert wf._refresh_hours() == 2


def test_resolve_weather_path_env(tmp_path, monkeypatch):
    # absolute path from env
    p = tmp_path / "wf.csv"
    p.write_text("timestamp,foo\n")
    monkeypatch.setenv("WEATHER_FORECAST_PATH", str(p))
    got = wf._resolve_weather_path()
    assert got == Path(str(p))

    # empty env -> falls back to default path inside repo
    monkeypatch.delenv("WEATHER_FORECAST_PATH", raising=False)
    monkeypatch.setenv("WEATHER_FORECAST_PATH", "")
    got2 = wf._resolve_weather_path()
    assert got2 is not None and got2.name.endswith("weather_forecast.csv")
