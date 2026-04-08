import csv
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.fallback import bikes_station_predictor as bsp


def test_build_station_id_cases():
    assert bsp._build_station_id("123", None, None, None) == "123"
    assert bsp._build_station_id(None, 53.0, -6.0, None).startswith("lat:")
    assert bsp._build_station_id(None, None, None, "Main St") == "name:main st"
    assert bsp._build_station_id(None, None, None, None) is None


def test_parse_float_and_timestamp_variants():
    assert bsp._parse_float("12.3") == 12.3
    assert bsp._parse_float("") is None

    ts = bsp._parse_timestamp("2024-01-01T00:00:00Z")
    assert ts is not None and ts.tzinfo is not None

    ts2 = bsp._parse_timestamp("01/01/2024 00:00")
    assert ts2 is not None

    ts3 = bsp._parse_timestamp(str(1609459200))
    assert ts3 is not None


def test_station_history_model_load_and_predict(tmp_path):
    file = tmp_path / "stations.csv"
    with file.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["timestamp", "station_id", "available_bikes", "available_docks", "total", "name", "lat", "lon"],
        )
        writer.writeheader()
        # create two stations with same station_id but different hours
        writer.writerow(
            {
                "timestamp": "2024-01-01T09:00:00Z",
                "station_id": "s1",
                "available_bikes": "2",
                "available_docks": "3",
                "total": "5",
                "name": "S1",
                "lat": "53.0",
                "lon": "-6.0",
            }
        )
        writer.writerow(
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "station_id": "s2",
                "available_bikes": "4",
                "available_docks": "1",
                "total": "5",
                "name": "S2",
                "lat": "53.1",
                "lon": "-6.1",
            }
        )

    model = bsp.BikeStationHistoryModel(file)
    assert model.load() is True
    assert model.total_rows == 2

    # predict at hour 9 -> should include s1
    now = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    preds = model.predict(now)
    assert any(p["station_id"] == "s1" for p in preds)

    # predict at an unrelated hour -> fall back to overall average
    now2 = datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc)
    preds2 = model.predict(now2)
    assert isinstance(preds2, list)


def test_aggregate_station_predictions():
    stations = [
        {"free_bikes": 1, "empty_slots": 2},
        {"free_bikes": 3, "empty_slots": 4},
    ]
    bikes, docks, reporting = bsp.aggregate_station_predictions(stations)
    assert bikes == 4
    assert docks == 6
    assert reporting == 2


def test_predict_bike_stations_monkeypatch(monkeypatch):
    # monkeypatch the function used by this module (it was imported at module import)
    monkeypatch.setattr(
        "backend.fallback.bikes_station_predictor.predict_stations",
        lambda now=None: [{"free_bikes": 1, "empty_slots": 2}],
    )
    res = bsp.predict_bike_stations(now=datetime.now(timezone.utc))
    assert res is not None
    assert res.snapshot is not None
    assert isinstance(res.snapshot, list)
