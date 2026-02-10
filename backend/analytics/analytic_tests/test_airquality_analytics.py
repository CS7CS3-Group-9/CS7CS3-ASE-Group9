import pytest
from backend.models.airquality_models import PollutantLevels, AirQualityMetrics
from backend.analytics.airquality_analytics import (
    categorise_aqi,
    check_pollutant_safety,
    overall_air_quality_level,
    count_unsafe_pollutants,
)


def test_categorize_aqi_low():
    metrics = AirQualityMetrics(aqi_value=35, pollutants=None)
    assert categorise_aqi(metrics) == "low"


def test_categorize_aqi_medium():
    metrics = AirQualityMetrics(aqi_value=75, pollutants=None)
    assert categorise_aqi(metrics) == "medium"


def test_categorize_aqi_high():
    metrics = AirQualityMetrics(aqi_value=150, pollutants=None)
    assert categorise_aqi(metrics) == "high"


def test_pollutant_safety_all_safe():
    pollutants = PollutantLevels(
        pm2_5=5, pm10=10, nitrogen_dioxide=10, carbon_monoxide=0.5, ozone=50, sulphur_dioxide=5, units={}
    )
    metrics = AirQualityMetrics(aqi_value=35, pollutants=pollutants)
    result = check_pollutant_safety(metrics)
    assert all(level == "safe" for level in result.values())


def test_pollutant_safety_some_unsafe():
    pollutants = PollutantLevels(
        pm2_5=80, pm10=10, nitrogen_dioxide=50, carbon_monoxide=0.5, ozone=50, sulphur_dioxide=5, units={}
    )
    metrics = AirQualityMetrics(aqi_value=35, pollutants=pollutants)
    result = check_pollutant_safety(metrics)
    assert result["pm2_5"] == "unsafe"
    assert result["nitrogen_dioxide"] == "unsafe"
    assert result["pm10"] == "safe"


def test_count_unsafe_pollutants_none():
    pollutants = PollutantLevels(
        pm2_5=10, pm10=10, nitrogen_dioxide=10, carbon_monoxide=1, ozone=50, sulphur_dioxide=10, units={}
    )
    metrics = AirQualityMetrics(aqi_value=35, pollutants=pollutants)
    assert count_unsafe_pollutants(metrics) == 0


def test_count_unsafe_pollutants_some():
    pollutants = PollutantLevels(
        pm2_5=30, pm10=55, nitrogen_dioxide=10, carbon_monoxide=15, ozone=50, sulphur_dioxide=25, units={}
    )
    metrics = AirQualityMetrics(aqi_value=35, pollutants=pollutants)
    assert count_unsafe_pollutants(metrics) == 4


def test_overall_air_quality_low():
    pollutants = PollutantLevels(
        pm2_5=5, pm10=10, nitrogen_dioxide=10, carbon_monoxide=1, ozone=50, sulphur_dioxide=5, units={}
    )
    metrics = AirQualityMetrics(aqi_value=40, pollutants=pollutants)
    assert overall_air_quality_level(metrics) == "low"


def test_overall_air_quality_medium_due_to_aqi():
    pollutants = PollutantLevels(
        pm2_5=5, pm10=10, nitrogen_dioxide=10, carbon_monoxide=1, ozone=50, sulphur_dioxide=5, units={}
    )
    metrics = AirQualityMetrics(aqi_value=80, pollutants=pollutants)
    assert overall_air_quality_level(metrics) == "medium"


def test_overall_air_quality_medium_due_to_few_unsafe_pollutants():
    pollutants = PollutantLevels(
        pm2_5=30, pm10=10, nitrogen_dioxide=10, carbon_monoxide=1, ozone=50, sulphur_dioxide=5, units={}
    )
    metrics = AirQualityMetrics(aqi_value=40, pollutants=pollutants)
    # Only pm2_5 is unsafe → medium
    assert overall_air_quality_level(metrics) == "medium"


def test_overall_air_quality_high_due_to_aqi():
    pollutants = PollutantLevels(
        pm2_5=5, pm10=10, nitrogen_dioxide=10, carbon_monoxide=1, ozone=50, sulphur_dioxide=5, units={}
    )
    metrics = AirQualityMetrics(aqi_value=150, pollutants=pollutants)
    assert overall_air_quality_level(metrics) == "high"


def test_overall_air_quality_high_due_to_many_unsafe_pollutants():
    pollutants = PollutantLevels(
        pm2_5=30, pm10=55, nitrogen_dioxide=50, carbon_monoxide=15, ozone=50, sulphur_dioxide=25, units={}
    )
    metrics = AirQualityMetrics(aqi_value=40, pollutants=pollutants)
    # 4 pollutants unsafe → high
    assert overall_air_quality_level(metrics) == "high"
