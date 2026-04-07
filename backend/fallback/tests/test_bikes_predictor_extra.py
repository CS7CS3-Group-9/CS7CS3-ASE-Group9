import os
from datetime import datetime, timezone
from pathlib import Path
import csv

import pytest

from backend.fallback import bikes_predictor as bp
from backend.models.bike_models import BikeMetrics


def test_hourstats_add_and_averages():
    h = bp.HourStats()
    assert h.averages() is None
    h.add(10, 5, 2)
    h.add(20, 15, 3)
    av = h.averages()
    assert av is not None
    bikes_avg, docks_avg, stations_avg = av
    assert bikes_avg == pytest.approx(15.0)
    assert docks_avg == pytest.approx(10.0)
    assert stations_avg == pytest.approx(2.5)


def test_parse_float_and_timestamp():
    assert bp._parse_float("10.5") == 10.5
    assert bp._parse_float("") is None
    assert bp._parse_float(None) is None

    # ISO with Z
    ts = bp._parse_timestamp("2024-01-01T12:00:00Z")
    assert ts is not None and ts.tzinfo is not None

    # epoch
    ts2 = bp._parse_timestamp(str(1609459200))
    assert ts2 is not None and ts2.tzinfo is not None

    # invalid
    assert bp._parse_timestamp("") is None


def test_resolve_history_path_env(tmp_path, monkeypatch):
    file = tmp_path / "bikes_history.csv"
    file.write_text("timestamp,available_bikes,available_docks,stations_reporting\n")
    monkeypatch.setenv("BIKES_HISTORY_PATH", str(file))
    path = bp._resolve_history_path()
    assert path is not None
    assert Path(path).resolve() == file.resolve()


def test_bikehistorymodel_load_and_predict(tmp_path):
    # create CSV with two rows at hour 9 and 10 UTC
    file = tmp_path / "bikes_history.csv"
    with file.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["timestamp", "available_bikes", "available_docks", "stations_reporting"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "timestamp": "2024-01-01T09:00:00Z",
                "available_bikes": "10",
                "available_docks": "5",
                "stations_reporting": "3",
            }
        )
        writer.writerow(
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "available_bikes": "20",
                "available_docks": "15",
                "stations_reporting": "4",
            }
        )

    model = bp.BikeHistoryModel(file)
    assert model.load() is True
    assert model.total_rows == 2

    # predict at hour 9 -> should use hour stats
    now = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    res = model.predict(now)
    assert res is not None
    metrics, confidence, reason = res
    assert isinstance(metrics, BikeMetrics)
    assert metrics.available_bikes in (9, 10, 11)  # rounding
    assert reason in ("historical_hourly_average", "historical_overall_average")


def test_infer_location():
    class Dummy:
        pass

    d = Dummy()
    assert bp._infer_location(None) == "dublin"
    d.location = "north"
    assert bp._infer_location(d) == "north"


def test_predict_bikes_snapshot_monkeypatch(monkeypatch):
    # monkeypatch the bikes_station_predictor.predict_bike_stations to return a small PredictionResult-like object
    from backend.fallback.predictor import PredictionResult

    class FakePR:
        def __init__(self, snapshot):
            self.snapshot = snapshot
            self.based_on = None
            self.confidence = 0.5
            self.reason = "station_prediction"

    def fake_predict(now=None):
        # return snapshot as list of station dicts
        stations = [
            {"free_bikes": 3, "empty_slots": 2},
            {"free_bikes": 5, "empty_slots": 1},
        ]
        return FakePR(stations)

    monkeypatch.setattr("backend.fallback.bikes_station_predictor.predict_bike_stations", fake_predict)

    result = bp.predict_bikes_snapshot(cached_snapshot=None, now=datetime.now(timezone.utc))
    assert result is not None
    assert result.snapshot.bikes.available_bikes == 8
    assert result.snapshot.bikes.available_docks == 3
    assert result.confidence == 0.5
    assert result.reason.startswith("from_")
