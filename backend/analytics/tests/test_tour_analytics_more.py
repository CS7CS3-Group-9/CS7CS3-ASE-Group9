from backend.analytics import tour_analytics as ta


def test_get_tour_type_distribution():
    tours = [{"type": "Museum"}, {"type": "Museum"}, {"type": "Free"}, {}]
    dist = ta.get_tour_type_distribution(tours)
    assert dist["Museum"] == 2
    assert dist["Free"] == 1
    assert dist.get("Unknown") == 1


def test_get_distance_statistics_empty_and_nonempty():
    empty = ta.get_distance_statistics([])
    assert empty["closest"] is None and empty["farthest"] is None and empty["average_distance"] == 0

    tours = [
        {"name": "A", "distance_km": 1.0, "type": "X"},
        {"name": "B", "distance_km": 3.0, "type": "Y"},
    ]
    stats = ta.get_distance_statistics(tours)
    assert stats["closest"]["name"] == "A"
    assert stats["farthest"]["name"] == "B"
    assert stats["average_distance"] == 2.0


def test_detect_tours_by_distance():
    tours = [
        {"name": "Near", "distance_km": 1.0, "type": "X"},
        {"name": "Far", "distance_km": 10.0, "type": "Y"},
        {"name": "None", "distance_km": None},
    ]
    walking, distant = ta.detect_tours_by_distance(tours, very_close_threshold=2.5)
    assert any(t["tour"] == "Near" for t in walking)
    assert any(t["tour"] == "Far" for t in distant)


def test_get_tours_by_type_case_insensitive():
    tours = [{"type": "Museum"}, {"type": "museum"}, {"type": "Free"}]
    m = ta.get_tours_by_type(tours, "museum")
    assert len(m) == 2


def test_calculate_area_coverage_and_distance():
    tours = [
        {"latitude": 53.3498, "longitude": -6.2603},
        {"latitude": 53.3508, "longitude": -6.2613},
    ]
    cov = ta.calculate_area_coverage(tours)
    assert cov["bounding_box"]["min_latitude"] <= cov["center_point"]["latitude"] <= cov["bounding_box"]["max_latitude"]
    assert cov["radius_km"] >= 0


def test_generate_and_print_report(capsys):
    tours = [{"name": "T1", "distance_km": 0.5, "type": "Museum", "latitude": 53.3498, "longitude": -6.26}]
    report = ta.generate_analytics_report(tours)
    ta.print_analytics_report(report)
    captured = capsys.readouterr()
    assert "TOUR ANALYTICS REPORT" in captured.out
