from backend.analytics import tour_analytics as ta


def make_sample_tours():
    return [
        {"name": "A", "type": "Museum", "distance_km": 0.5, "latitude": 53.35, "longitude": -6.26},
        {"name": "B", "type": "Free", "distance_km": 10.0, "latitude": 53.36, "longitude": -6.25},
        {"name": "C", "type": "Museum", "distance_km": 2.0, "latitude": 53.37, "longitude": -6.24},
    ]


def test_get_tour_type_distribution():
    tours = make_sample_tours()
    dist = ta.get_tour_type_distribution(tours)
    assert dist["Museum"] == 2


def test_get_distance_statistics():
    tours = make_sample_tours()
    stats = ta.get_distance_statistics(tours)
    assert "closest" in stats and "farthest" in stats


def test_detect_tours_by_distance():
    tours = make_sample_tours()
    walking, distant = ta.detect_tours_by_distance(tours, very_close_threshold=1.0)
    assert any(t["level"] == "walking_distance" for t in walking)
    assert any(d["level"] == "distant" for d in distant)


def test_get_tours_by_type():
    tours = make_sample_tours()
    filtered = ta.get_tours_by_type(tours, "museum")
    assert len(filtered) == 2


def test_calculate_area_coverage_empty():
    assert ta.calculate_area_coverage([])["radius_km"] == 0


def test_calculate_distance():
    d = ta.calculate_distance(53.3498, -6.2603, 53.3498, -6.2603)
    assert d == 0
