from datetime import datetime, timezone

from backend.ml.bikes_model import _build_feature_row, _apply_weather_adjustment


def test_build_feature_row_basic():
    now = datetime(2026, 3, 9, 8, 15, tzinfo=timezone.utc)
    station = {"lat": 53.1, "lon": -6.2, "capacity": 15}
    row = _build_feature_row(now, station, {}, [])
    assert row["hour"] == 8.0
    assert row["lat"] == 53.1
    assert row["capacity"] == 15.0


def test_apply_weather_adjustment_thresholds():
    # no rain
    bikes, factor, reason = _apply_weather_adjustment(10, 15, {})
    assert bikes == 10 and factor is None

    # light rain
    bikes2, factor2, reason2 = _apply_weather_adjustment(10, 15, {"weather_rain": 1.0})
    assert factor2 == 0.9 and reason2 == "light_rain"

    # heavy rain clipped by capacity
    bikes3, factor3, reason3 = _apply_weather_adjustment(20, 10, {"weather_rain": 6.0})
    assert bikes3 <= 10 and reason3 == "heavy_rain"
