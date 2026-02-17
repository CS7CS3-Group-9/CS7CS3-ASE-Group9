import pytest
import math
from backend.models.bus_models import BusStop, BusMetrics
from backend.analytics.bus_analytics import (
    calculate_distance,
    get_stop_frequencies,
    detect_low_frequency_stops,
    detect_high_frequency_stops,
    get_stop_spread,
    get_isolated_stops,
    get_frequency_statistics,
    find_nearest_stop_distance,
    get_population_coverage_metrics,
    identify_underserved_populations,
    get_stop_density_around_population,
)


# Helper to create mock stops
def create_mock_stop(stop_id: str, name: str, lat: float, lon: float) -> BusStop:
    return BusStop(stop_id=stop_id, name=name, lat=lat, longitude=lon)


# --- Existing tests (stop‑only) ---


def test_calculate_distance():
    dist = calculate_distance(53.3498, -6.2603, 53.3498, -6.2703)
    assert 0.6 < dist < 0.8


def test_get_stop_frequencies():
    stops = [create_mock_stop("S1", "Stop 1", 53.35, -6.26)]
    freqs = {"S1": 5}
    metrics = BusMetrics(stops=stops, stop_frequencies=freqs)
    assert get_stop_frequencies(metrics) == freqs


def test_detect_low_frequency_stops():
    stops = [create_mock_stop("S1", "Stop 1", 53.35, -6.26)]
    freqs = {"S1": 5}
    metrics = BusMetrics(stops=stops, stop_frequencies=freqs)
    result = detect_low_frequency_stops(metrics, threshold=10)
    assert len(result) == 1
    assert result[0]["stop_id"] == "S1"
    assert result[0]["frequency"] == 5
    assert result[0]["level"] == "low"


def test_detect_high_frequency_stops():
    stops = [create_mock_stop("S1", "Stop 1", 53.35, -6.26)]
    freqs = {"S1": 120}
    metrics = BusMetrics(stops=stops, stop_frequencies=freqs)
    result = detect_high_frequency_stops(metrics, threshold=100)
    assert len(result) == 1
    assert result[0]["stop_id"] == "S1"
    assert result[0]["frequency"] == 120
    assert result[0]["level"] == "high"


def test_get_stop_spread():
    stops = [
        create_mock_stop("S1", "Stop 1", 53.35, -6.26),
        create_mock_stop("S2", "Stop 2", 53.36, -6.27),
    ]
    metrics = BusMetrics(stops=stops)
    result = get_stop_spread(metrics)
    assert result["total_stops"] == 2
    assert result["bounding_box"]["min_lat"] == 53.35
    assert result["center_point"]["lat"] == 53.355
    assert result["average_distance_from_center"] > 0


def test_get_stop_spread_empty():
    metrics = BusMetrics(stops=[])
    result = get_stop_spread(metrics)
    assert result["bounding_box"] is None


def test_get_isolated_stops():
    stops = [
        create_mock_stop("S1", "Stop 1", 53.35, -6.26),
        create_mock_stop("S2", "Stop 2", 53.36, -6.27),
        create_mock_stop("S3", "Stop 3", 53.40, -6.30),
    ]
    metrics = BusMetrics(stops=stops)
    result = get_isolated_stops(metrics, distance_threshold=3.0)
    assert len(result) == 1
    assert result[0]["stop_id"] == "S3"
    assert result[0]["distance_to_nearest"] > 3.0


def test_get_isolated_stops_less_than_two():
    metrics = BusMetrics(stops=[create_mock_stop("S1", "Stop 1", 53.35, -6.26)])
    result = get_isolated_stops(metrics)
    assert result == []


def test_get_frequency_statistics():
    stops = [create_mock_stop(f"S{i}", f"Stop {i}", 53.35, -6.26) for i in range(1, 4)]
    freqs = {"S1": 5, "S2": 15, "S3": 20}
    metrics = BusMetrics(stops=stops, stop_frequencies=freqs)
    result = get_frequency_statistics(metrics)
    assert result["min_frequency"] == 5
    assert result["max_frequency"] == 20
    # Use approx because we round to 1 decimal
    assert result["average_frequency"] == pytest.approx(13.3, abs=0.1)
    assert result["total_trips"] == 40
    assert result["stops_with_data"] == 3


def test_get_frequency_statistics_empty():
    metrics = BusMetrics(stops=[], stop_frequencies={})
    result = get_frequency_statistics(metrics)
    assert result["min_frequency"] == 0


# --- New tests for population analytics ---


def test_find_nearest_stop_distance():
    stops = [
        create_mock_stop("S1", "Stop 1", 53.35, -6.26),
        create_mock_stop("S2", "Stop 2", 53.36, -6.27),
    ]
    # Point slightly closer to S1 (53.352, -6.261)
    pop_lat, pop_lon = 53.352, -6.261
    nearest, dist = find_nearest_stop_distance(pop_lat, pop_lon, stops)
    assert nearest.stop_id == "S1"  # S1 is now closer
    assert 0.2 < dist < 0.4  # approximate distance range


def test_find_nearest_stop_distance_empty():
    nearest, dist = find_nearest_stop_distance(53.35, -6.26, [])
    assert nearest is None
    assert dist == float("inf")


def test_get_population_coverage_metrics():
    population = [
        {"name": "Town A", "pop": 5000, "lat": 53.35, "lon": -6.26},
        {"name": "Town B", "pop": 3000, "lat": 53.38, "lon": -6.30},
    ]
    stops = [
        create_mock_stop("S1", "Stop 1", 53.35, -6.26),  # exactly at Town A
        create_mock_stop("S2", "Stop 2", 53.37, -6.28),  # ~1.73 km from Town B
    ]
    result = get_population_coverage_metrics(population, stops)
    assert result["total_population_centres"] == 2
    assert result["min_distance"] == 0.0
    assert result["max_distance"] > 1.0
    # Town A within 1km, Town B within 2km (but >1km)
    assert result["centres_within_1km"] == 1
    assert result["centres_within_2km"] == 1
    assert result["centres_beyond_2km"] == 0
    assert len(result["details"]) == 2


def test_get_population_coverage_metrics_no_stops():
    population = [{"name": "Town A", "pop": 5000, "lat": 53.35, "lon": -6.26}]
    result = get_population_coverage_metrics(population, [])
    assert result["total_population_centres"] == 1
    assert result["average_distance"] == 0


def test_identify_underserved_populations():
    population = [
        {"name": "Town A", "pop": 5000, "lat": 53.35, "lon": -6.26},
        {"name": "Town B", "pop": 3000, "lat": 53.45, "lon": -6.40},
    ]
    stops = [create_mock_stop("S1", "Stop 1", 53.35, -6.26)]
    result = identify_underserved_populations(population, stops, threshold_km=2.0)
    assert len(result) == 1
    assert result[0]["name"] == "Town B"
    assert result[0]["distance_to_nearest_stop_km"] > 2.0


def test_identify_underserved_populations_no_stops():
    population = [{"name": "Town A", "pop": 5000, "lat": 53.35, "lon": -6.26}]
    result = identify_underserved_populations(population, [], threshold_km=2.0)
    assert len(result) == 1  # every point is underserved when no stops


def test_get_stop_density_around_population():
    population = [{"name": "Town A", "pop": 5000, "lat": 53.35, "lon": -6.26}]
    stops = [
        create_mock_stop("S1", "Stop 1", 53.35, -6.26),
        create_mock_stop("S2", "Stop 2", 53.36, -6.27),
    ]
    result = get_stop_density_around_population(population, stops, radius_km=1.0)
    assert result[0]["stops_within_1.0km"] == 1
