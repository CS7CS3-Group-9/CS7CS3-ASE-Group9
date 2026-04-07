import os
from datetime import datetime, timezone

import pytest

from backend.adapters.bus_adapter import BusAdapter


def test_parse_gtfs_time_to_seconds_valid_and_invalid():
    b = BusAdapter(gtfs_path=".")
    assert b._parse_gtfs_time_to_seconds("00:00:00") == 0
    assert b._parse_gtfs_time_to_seconds("01:02:03") == 3723
    assert b._parse_gtfs_time_to_seconds("") is None
    assert b._parse_gtfs_time_to_seconds(None) is None
    # invalid parts
    assert b._parse_gtfs_time_to_seconds("1:2") is None
    assert b._parse_gtfs_time_to_seconds("aa:bb:cc") is None
    # out of range
    assert b._parse_gtfs_time_to_seconds("00:60:00") is None
    assert b._parse_gtfs_time_to_seconds("00:00:60") is None


def test_count_stop_frequencies_and_arrivals(tmp_path, monkeypatch):
    # create GTFS-like files in tmp_path
    # BusAdapter expects files under a GTFS/ subdirectory; create that
    gtfs = tmp_path / "GTFS"
    gtfs.mkdir()
    stops = gtfs / "stops.txt"
    stop_times = gtfs / "stop_times.txt"
    stops.write_text("stop_id,stop_name,stop_lat,stop_lon\n1,One,53.35,-6.26\n2,Two,52.0,-7.0\n")
    # arrival_time at 12:00:00 and 13:30:00
    stop_times.write_text(
        "trip_id,arrival_time,departure_time,stop_id\n"
        + "t1,12:00:00,12:00:00,1\n"
        + "t2,13:30:00,13:30:00,1\n"
        + "t3,12:15:00,12:15:00,2\n"
    )

    b = BusAdapter(gtfs_path=str(tmp_path))

    # ensure resolver finds our files
    assert b._resolve_stops_file().exists()
    assert b._resolve_stop_times_file().exists()

    # frequencies should count only stop_id '1' (inside Dublin bbox)
    freqs = b._count_stop_frequencies(dublin_stop_ids={"1"})
    assert freqs.get("1") == 2

    # test arrivals within hour by using a fixed now_local (11:30 -> 12:30 window)
    now_local = datetime(2026, 1, 1, 11, 30, tzinfo=timezone.utc)
    arrivals = b._count_arrivals_within_hour(dublin_stop_ids={"1", "2"}, now_local=now_local)
    # trips at 12:00:00 (stop 1) and 12:15:00 (stop 2) fall within the 11:30-12:30 window
    assert arrivals.get("1") == 1
    assert arrivals.get("2") == 1
