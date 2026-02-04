import pytest

from backend.models.traffic_models import TrafficIncident
from backend.analytics.traffic_analytics import build_traffic_metrics


@pytest.fixture
def incidents_14():
    """14 incidents matching your mock API data"""
    return [
        TrafficIncident("Jam", "Major", "Stationary traffic", "A", "B", "Unknown road", 91.0335578732, 85, 1.4),
        TrafficIncident("Jam", "Major", "Stationary traffic", "A", "B", "Unknown road", 191.0632476919, 178, 3.0),
        TrafficIncident("Jam", "Major", "Stationary traffic", "A", "B", "Unknown road", 104.9745249761, 112, 1.9),
        TrafficIncident("Jam", "Major", "Stationary traffic", "A", "B", "Unknown road", 158.488704609, 139, 2.3),
        TrafficIncident("Jam", "Major", "Stationary traffic", "A", "B", "Unknown road", 40.7695392422, 76, 1.3),
        TrafficIncident("Jam", "Major", "Stationary traffic", "A", "B", "Unknown road", 205.5532124722, 231, 3.9),
        TrafficIncident("Jam", "Moderate", "Queuing traffic", "A", "B", "R108, N1", 725.2961172375, 268, 4.5),
        TrafficIncident("Jam", "Moderate", "Queuing traffic", "A", "B", "N81", 688.6191833754, 284, 4.7),
        TrafficIncident("Jam", "Moderate", "Queuing traffic", "A", "B", "Unknown road", 114.1159500372, 110, 1.8),
        TrafficIncident("Jam", "Moderate", "Queuing traffic", "A", "B", "N4", 1120.4530749383, 369, 6.2),
        TrafficIncident("Jam", "Minor", "Slow traffic", "A", "B", "R108, N1", 411.171, 133, 2.2),
        TrafficIncident("Jam", "Minor", "Slow traffic", "A", "B", "R114", 585.0126486495, 213, 3.5),
        TrafficIncident("Jam", "Minor", "Slow traffic", "A", "B", "R114", 334.9766140326, 183, 3.0),
        TrafficIncident("Road Closed", "Undefined", "Closed", "A", "B", "Unknown road", 93.7069267635, None, 0),
    ]


def test_metrics_total_incidents(incidents_14):
    metrics = build_traffic_metrics(incidents_14, radius_km=0.5)
    assert metrics.total_incidents == 14


def test_incidents_by_category(incidents_14):
    metrics = build_traffic_metrics(incidents_14, radius_km=0.5)
    assert metrics.incidents_by_category["Jam"] == 13
    assert metrics.incidents_by_category["Road Closed"] == 1


def test_incidents_by_severity(incidents_14):
    metrics = build_traffic_metrics(incidents_14, radius_km=0.5)
    assert metrics.incidents_by_severity["Major"] == 6
    assert metrics.incidents_by_severity["Moderate"] == 4
    assert metrics.incidents_by_severity["Minor"] == 3
    assert metrics.incidents_by_severity["Undefined"] == 1


def test_total_delay_minutes(incidents_14):
    metrics = build_traffic_metrics(incidents_14, radius_km=0.5)
    assert metrics.total_delay_minutes == pytest.approx(39.7, 0.1)


def test_average_delay_minutes(incidents_14):
    metrics = build_traffic_metrics(incidents_14, radius_km=0.5)
    assert metrics.average_delay_minutes == pytest.approx(2.836, 0.01)


def test_congestion_level_high(incidents_14):
    metrics = build_traffic_metrics(incidents_14, radius_km=0.5)
    assert metrics.congestion_level == "high"


def test_congestion_level_low():
    incidents = [TrafficIncident("Jam", "Minor", "Slow traffic", "A", "B", "R123", 100, 30, 0.5)]
    metrics = build_traffic_metrics(incidents, radius_km=5.0)
    assert metrics.congestion_level == "low"


def test_empty_incidents_defaults():
    metrics = build_traffic_metrics([], radius_km=5.0)
    assert metrics.total_incidents == 0
    assert metrics.incidents_by_category == {}
    assert metrics.incidents_by_severity == {}
    assert metrics.total_delay_minutes == 0
    assert metrics.average_delay_minutes == 0
    assert metrics.congestion_level == "low"
