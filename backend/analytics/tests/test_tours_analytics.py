import os
import pytest
from typing import List, Dict
from backend.analytics.tour_analytics import (
    get_tour_type_distribution,
    get_distance_statistics,
    detect_tours_by_distance,
    get_tours_by_type,
)

# Sample test data matching the structure from your API
SAMPLE_TOURS = [
    {"name": "National Museum", "type": "Museum", "latitude": 53.3404, "longitude": -6.2541, "distance_km": 0.5},
    {"name": "Dublin Castle", "type": "Castle", "latitude": 53.3431, "longitude": -6.2675, "distance_km": 1.2},
    {
        "name": "St. Patrick's Cathedral",
        "type": "Cathedral",
        "latitude": 53.3395,
        "longitude": -6.2712,
        "distance_km": 1.8,
    },
    {"name": "Guinness Storehouse", "type": "Brewery", "latitude": 53.3418, "longitude": -6.2868, "distance_km": 2.5},
    {"name": "Trinity College", "type": "University", "latitude": 53.3438, "longitude": -6.2544, "distance_km": 0.3},
    {
        "name": "Kilmainham Gaol",
        "type": "Historic Prison",
        "latitude": 53.3419,
        "longitude": -6.3095,
        "distance_km": 3.8,
    },
    {"name": "Phoenix Park", "type": "Park", "latitude": 53.3564, "longitude": -6.3291, "distance_km": 4.2},
    {"name": "Jameson Distillery", "type": "Distillery", "latitude": 53.3477, "longitude": -6.2787, "distance_km": 1.5},
]


def test_get_tour_type_distribution():
    """Test distribution of tour types."""
    result = get_tour_type_distribution(SAMPLE_TOURS)

    assert isinstance(result, dict)
    assert result["Museum"] == 1
    assert result["Castle"] == 1

    # Test with empty list
    assert get_tour_type_distribution([]) == {}


def test_get_distance_statistics():
    """Test distance statistics calculation."""
    result = get_distance_statistics(SAMPLE_TOURS)

    assert isinstance(result, dict)
    assert result["closest"]["name"] == "Trinity College"
    assert result["closest"]["distance_km"] == 0.3
    assert result["farthest"]["name"] == "Phoenix Park"
    assert result["farthest"]["distance_km"] == 4.2
    assert 0.3 <= result["average_distance"] <= 4.2

    # Test with empty list
    empty_result = get_distance_statistics([])
    assert empty_result["average_distance"] == 0
    assert empty_result["closest"] is None
    assert empty_result["farthest"] is None


def test_detect_tours_by_distance():
    """Test separation of tours into walking distance and distant tours."""

    # Test with default threshold (2.5km)
    walking_tours, distant_tours = detect_tours_by_distance(SAMPLE_TOURS)

    assert isinstance(walking_tours, list)
    assert isinstance(distant_tours, list)

    # Test walking tours are within 2.5km
    for tour in walking_tours:
        assert tour["distance"] <= 2.5
        assert tour["level"] == "walking_distance"

    # Test distant tours are beyond 2.5km
    for tour in distant_tours:
        assert tour["distance"] > 2.5
        assert tour["level"] == "distant"

    # No tour should be in both lists
    walking_names = {t["tour"] for t in walking_tours}
    distant_names = {t["tour"] for t in distant_tours}
    assert len(walking_names.intersection(distant_names)) == 0

    # All tours with distances should be accounted for
    total_tours_with_distance = sum(1 for t in SAMPLE_TOURS if t.get("distance_km") is not None)
    assert len(walking_tours) + len(distant_tours) == total_tours_with_distance

    # Test with custom threshold (1.0km)
    walking_tours_custom, distant_tours_custom = detect_tours_by_distance(SAMPLE_TOURS, very_close_threshold=1.0)

    # Verify custom threshold works
    for tour in walking_tours_custom:
        assert tour["distance"] <= 1.0

    for tour in distant_tours_custom:
        assert tour["distance"] > 1.0

    # With lower threshold, should have fewer walking tours
    assert len(walking_tours_custom) <= len(walking_tours)
    assert len(distant_tours_custom) >= len(distant_tours)

    # Test edge case: threshold higher than all tours
    all_walking, none_distant = detect_tours_by_distance(
        SAMPLE_TOURS, very_close_threshold=100.0  # Higher than any tour distance
    )
    assert len(all_walking) == total_tours_with_distance
    assert len(none_distant) == 0

    # Test edge case: threshold lower than all tours
    none_walking, all_distant = detect_tours_by_distance(
        SAMPLE_TOURS, very_close_threshold=0.0  # Lower than any tour distance
    )
    assert len(none_walking) == 0
    assert len(all_distant) == total_tours_with_distance


def test_get_tours_by_type():
    """Test filtering tours by type."""
    museums = get_tours_by_type(SAMPLE_TOURS, "Museum")
    assert len(museums) == 1
    assert museums[0]["name"] == "National Museum"

    # Test non-existent type
    nonexistent = get_tours_by_type(SAMPLE_TOURS, "Nonexistent")
    assert len(nonexistent) == 0

    # Test with empty list
    assert get_tours_by_type([], "Museum") == []


def test_edge_cases():
    """Test various edge cases."""
    # Test with None input
    with pytest.raises(TypeError):
        get_tour_type_distribution(None)

    # Test with invalid tour data
    invalid_tours = [{"name": "Invalid"}]
    result = get_distance_statistics(invalid_tours)
    assert result["average_distance"] == 0


def test_tour_with_missing_fields():
    """Test handling of tours with missing fields."""
    incomplete_tours = [
        {"name": "Tour 1"},  # Missing all other fields
        {"name": "Tour 2", "distance_km": 1.5},  # Missing type
        {"name": "Tour 3", "type": "Museum"},  # Missing distance
    ]

    # These should all handle missing fields gracefully
    distribution = get_tour_type_distribution(incomplete_tours)
    assert isinstance(distribution, dict)

    stats = get_distance_statistics(incomplete_tours)
    assert isinstance(stats, dict)

    walking_tours, distant_tours = detect_tours_by_distance(incomplete_tours)
    assert isinstance(walking_tours, list)
    assert isinstance(distant_tours, list)


if __name__ == "__main__":
    # Run tests manually if needed
    pytest.main([__file__, "-v"])
