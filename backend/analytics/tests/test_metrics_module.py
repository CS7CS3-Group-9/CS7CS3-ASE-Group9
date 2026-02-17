import math

from analytics.metrics import (
    estimate_emissions_kg,
    congestion_score,
    bike_availability_score,
    air_quality_score,
)
from models.traffic_models import TrafficMetrics
from models.bike_models import BikeMetrics
from models.airquality_models import AirQualityMetrics, PollutantLevels


def test_estimate_emissions_kg_default_car():
    assert estimate_emissions_kg(10.0) == 1.71


def test_estimate_emissions_kg_unknown_mode_defaults_to_car():
    assert estimate_emissions_kg(10.0, mode="unknown") == 1.71


def test_estimate_emissions_kg_negative_distance_raises():
    try:
        estimate_emissions_kg(-1.0)
        assert False, "expected ValueError"
    except ValueError:
        assert True


def test_congestion_score_low_defaults():
    metrics = TrafficMetrics(
        congestion_level="low",
        average_speed=50,
        total_incidents=0,
        incidents_by_category={},
        incidents_by_severity={},
        total_delay_minutes=0,
        average_delay_minutes=0,
        incidents=[],
    )
    assert congestion_score(metrics) == 20.0


def test_congestion_score_caps_at_100():
    metrics = TrafficMetrics(
        congestion_level="high",
        average_speed=10,
        total_incidents=20,
        incidents_by_category={},
        incidents_by_severity={},
        total_delay_minutes=100,
        average_delay_minutes=50,
        incidents=[],
    )
    assert congestion_score(metrics) == 100.0


def test_bike_availability_score():
    metrics = BikeMetrics(available_bikes=3, available_docks=1, stations_reporting=1)
    assert bike_availability_score(metrics) == 75.0


def test_bike_availability_score_zero_total():
    metrics = BikeMetrics(available_bikes=0, available_docks=0, stations_reporting=0)
    assert bike_availability_score(metrics) == 0.0


def test_air_quality_score():
    pollutants = PollutantLevels(
        pm2_5=0, pm10=0, nitrogen_dioxide=0, carbon_monoxide=0, ozone=0, sulphur_dioxide=0, units={}
    )
    metrics = AirQualityMetrics(aqi_value=100, pollutants=pollutants)
    assert air_quality_score(metrics) == 50.0


def test_air_quality_score_clamps_high_aqi_to_zero():
    pollutants = PollutantLevels(
        pm2_5=0, pm10=0, nitrogen_dioxide=0, carbon_monoxide=0, ozone=0, sulphur_dioxide=0, units={}
    )
    metrics = AirQualityMetrics(aqi_value=250, pollutants=pollutants)
    assert air_quality_score(metrics) == 0.0
