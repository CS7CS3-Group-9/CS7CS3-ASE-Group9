from datetime import datetime, timezone

import pytest

from backend.fallback.bikes_station_predictor import (
    aggregate_station_predictions,
    predict_bike_stations,
)
from backend.ml.bikes_model import BikesModelBundle


def _write_dummy_model(tmp_path):
    try:
        from sklearn.dummy import DummyRegressor
        import numpy as np
        import joblib
    except Exception:
        pytest.skip("scikit-learn not available")

    feature_cols = [
        "hour",
        "weekday",
        "month",
        "day_of_year",
        "is_weekend",
        "lat",
        "lon",
        "capacity",
    ]

    X = np.array([[8, 1, 3, 60, 0, 53.1, -6.2, 15], [8, 1, 3, 60, 0, 53.2, -6.3, 10]])
    y = np.array([5.0, 10.0])
    model = DummyRegressor(strategy="mean")
    model.fit(X, y)

    stations = [
        {"station_id": "1", "name": "Station A", "lat": 53.1, "lon": -6.2, "capacity": 15},
        {"station_id": "2", "name": "Station B", "lat": 53.2, "lon": -6.3, "capacity": 10},
    ]

    bundle = BikesModelBundle(
        model=model,
        feature_columns=feature_cols,
        stations=stations,
        weather_feature_columns=[],
        trained_at=None,
    )

    model_path = tmp_path / "bikes_model.joblib"
    joblib.dump(bundle, model_path)
    return model_path


def test_predict_bike_stations_from_ml(monkeypatch, tmp_path):
    model_path = _write_dummy_model(tmp_path)
    monkeypatch.setenv("BIKES_MODEL_PATH", str(model_path))
    monkeypatch.setenv("WEATHER_AUTO_REFRESH", "false")
    monkeypatch.setenv("BIKES_WEATHER_ADJUSTMENT", "false")

    now = datetime(2026, 3, 9, 8, 15, tzinfo=timezone.utc)
    result = predict_bike_stations(now=now)

    assert result is not None
    stations = result.snapshot
    assert len(stations) == 2

    station_a = next(s for s in stations if s["station_id"] == "1")
    station_b = next(s for s in stations if s["station_id"] == "2")

    assert station_a["free_bikes"] == 8
    assert station_a["empty_slots"] == 7
    assert station_a["total"] == 15

    assert station_b["free_bikes"] == 8
    assert station_b["empty_slots"] == 2
    assert station_b["total"] == 10


def test_aggregate_station_predictions():
    stations = [
        {"free_bikes": 6, "empty_slots": 9},
        {"free_bikes": 4, "empty_slots": 6},
    ]
    bikes, docks, reporting = aggregate_station_predictions(stations)
    assert bikes == 10
    assert docks == 15
    assert reporting == 2
