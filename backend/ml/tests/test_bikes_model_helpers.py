import pytest
from datetime import datetime, timezone
from backend.ml.bikes_model import _apply_weather_adjustment, _build_feature_row


def test_apply_weather_adjustment_no_rain():
    bikes, factor, reason = _apply_weather_adjustment(10, 20, {})
    assert bikes == 10
    assert factor is None
    assert reason is None


def test_apply_weather_adjustment_light_moderate_heavy():
    bikes, factor, reason = _apply_weather_adjustment(10, None, {"weather_rain": 0.1})
    assert factor == pytest.approx(0.9)
    assert reason == "light_rain"
    bikes2, factor2, reason2 = _apply_weather_adjustment(10, None, {"weather_rain": 2.5})
    assert factor2 == pytest.approx(0.8)
    assert reason2 == "moderate_rain"
    bikes3, factor3, reason3 = _apply_weather_adjustment(10, None, {"weather_rain": 6.0})
    assert factor3 == pytest.approx(0.7)
    assert reason3 == "heavy_rain"


def test_build_feature_row_basic():
    now = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
    station = {"lat": 53.3, "lon": -6.2, "capacity": 20}
    weather = {"weather_rain": 0.0}
    row = _build_feature_row(now, station, weather, ["weather_rain"])
    assert row["hour"] == 9.0
    assert row["lat"] == 53.3
    assert "weather_rain" in row
