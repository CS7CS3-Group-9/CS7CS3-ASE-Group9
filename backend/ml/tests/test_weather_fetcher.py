from pathlib import Path
import tempfile
from datetime import datetime, timezone, timedelta

from backend.ml import weather_fetcher as wf


def test_normalise_header():
    assert wf._normalise_header("Time (UTC)") == "Time"
    assert wf._normalise_header("  temperature  ") == "temperature"
    assert wf._normalise_header("Rain (mm)") == "Rain"


def test_parse_open_meteo_csv_basic():
    csv_text = """header1,header2\nTime,Temp\n2024-01-01T00:00,5\n2024-01-01T01:00,6\n"""
    rows = wf._parse_open_meteo_csv(csv_text)
    assert isinstance(rows, list)
    # header names are normalised but case may be preserved; check lowercased keys
    keys_lower = {k.lower(): v for k, v in rows[0].items()}
    assert keys_lower["time"] == "2024-01-01T00:00"


def test_parse_open_meteo_csv_no_header():
    csv_text = """something,else\nno headers here\n"""
    rows = wf._parse_open_meteo_csv(csv_text)
    assert rows == []


def test_write_output_and_should_refresh(tmp_path):
    path = tmp_path / "forecast.csv"
    rows = [{"time": "2024-01-01T00:00", "temperature": "5"}]
    wf._write_output(path, rows)
    assert path.exists()
    # should_refresh False when fresh
    assert wf.should_refresh(path, refresh_hours=1000) is False
    # touch mtime to old
    old_time = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
    # use os.utime for cross-platform compatibility
    import os

    os.utime(str(path), (old_time, old_time))
    assert wf.should_refresh(path, refresh_hours=24) is True
