import pytest

from backend.models.bike_models import StationMetrics
from backend.analytics.bike_analytics import get_station_occupancy, detect_critical_occupancy


def test_calculates_occupancy_percentage_for_each_station():
    stations = [
        StationMetrics(name="Station A", free_bikes=5, empty_slots=15, total_spaces=20),
        StationMetrics(name="Station B", free_bikes=10, empty_slots=10, total_spaces=20),
    ]

    result = get_station_occupancy(stations)

    assert result["Station A"] == 25.0
    assert result["Station B"] == 50.0


def test_detects_low_occupancy_station():
    stations = [
        StationMetrics(name="Low Station", free_bikes=1, empty_slots=19, total_spaces=20),
        StationMetrics(name="Normal Station", free_bikes=10, empty_slots=10, total_spaces=20),
    ]

    result = detect_critical_occupancy(stations, low_threshold=10)

    assert len(result) == 1
    assert result[0]["station"] == "Low Station"
    assert result[0]["level"] == "low"


def test_detects_high_occupancy_station():
    stations = [StationMetrics(name="High Station", free_bikes=19, empty_slots=1, total_spaces=20)]

    result = detect_critical_occupancy(stations, high_threshold=90)

    assert len(result) == 1
    assert result[0]["station"] == "High Station"
    assert result[0]["level"] == "high"


def test_detects_both_high_and_low_stations():
    stations = [
        StationMetrics(name="Low", free_bikes=1, empty_slots=19, total_spaces=20),
        StationMetrics(name="High", free_bikes=19, empty_slots=1, total_spaces=20),
    ]

    result = detect_critical_occupancy(stations, low_threshold=10, high_threshold=90)

    levels = {r["station"]: r["level"] for r in result}

    assert levels["Low"] == "low"
    assert levels["High"] == "high"


def test_zero_capacity_station_is_ignored():
    stations = [StationMetrics(name="Broken Station", free_bikes=0, empty_slots=0, total_spaces=0)]

    result = detect_critical_occupancy(stations)

    assert result == []
