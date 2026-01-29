import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from backend.adapters.tour_adapter import TourAdapter


@pytest.fixture
def mock_overpass_response():
    """Sample response from Overpass API"""
    return {
        "version": 0.6,
        "generator": "Overpass API",
        "elements": [
            {
                "type": "node",
                "id": 7256089573,
                "lat": 53.4506340,
                "lon": -6.1583261,
                "tags": {
                    "name": "Casino Model Railway Museum",
                    "tourism": "museum",
                    "opening_hours": "Mo-Fr 11:00-18:00; Sa, Su 10:30-18:00",
                    "fee": "yes",
                    "phone": "+35361711222",
                    "website": "https://www.modelrailwaymuseum.ie",
                    "wheelchair": "yes",
                },
            },
            {
                "type": "way",
                "id": 326079832,
                "center": {"lat": 53.4449372, "lon": -6.1646051},
                "tags": {
                    "name": "Malahide Castle",
                    "historic": "castle",
                    "tourism": "attraction",
                    "fee": "no",
                    "wheelchair": "limited",
                },
            },
            {
                "type": "way",
                "id": 23403803,
                "center": {"lat": 53.4856523, "lon": -6.1674851},
                "tags": {
                    "name": "Newbridge House and Demesne",
                    "leisure": "park",
                    "tourism": "attraction",
                    "website": "https://newbridgehouseandfarm.com/",
                    "wheelchair": "yes",
                },
            },
        ],
    }


@pytest.fixture
def adapter():
    """Create adapter instance"""
    return TourAdapter()


def test_source_name(adapter):
    """Test source name returns 'tours'"""
    assert adapter.source_name() == "tours"


@patch("backend.adapters.tour_adapter.requests.post")
def test_fetch_success(mock_post, adapter, mock_overpass_response):
    """Test successful API fetch and parsing"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="donabate", radius_km=5)

    # Verify API was called
    mock_post.assert_called_once()

    # Verify snapshot structure
    assert snapshot.location == "donabate"
    assert isinstance(snapshot.timestamp, datetime)

    # tours should be an AttractionMetrics object
    assert snapshot.tours.total_attractions == 3


@patch("backend.adapters.tour_adapter.requests.post")
def test_attraction_parsing(mock_post, adapter, mock_overpass_response):
    """Test individual attractions are parsed correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="donabate", radius_km=5)
    attractions = snapshot.tours.attractions

    # Should have 3 attractions
    assert len(attractions) == 3

    # Check first attraction (museum)
    museum = attractions[0]
    assert museum.attraction_name == "Casino Model Railway Museum"
    assert museum.attraction_type == "museum"
    assert museum.latitude == 53.4506340
    assert museum.longitude == -6.1583261
    assert museum.open_times == "Mo-Fr 11:00-18:00; Sa, Su 10:30-18:00"
    assert museum.price == "yes"
    assert museum.phone == "+35361711222"
    assert museum.website == "https://www.modelrailwaymuseum.ie"
    assert museum.wheelchair_accessible == "yes"


@patch("backend.adapters.tour_adapter.requests.post")
def test_attraction_coordinates(mock_post, adapter, mock_overpass_response):
    """Test coordinates are extracted from both nodes and ways"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="donabate", radius_km=5)
    attractions = snapshot.tours.attractions

    # Node: lat/lon directly on element
    assert attractions[0].latitude == 53.4506340
    assert attractions[0].longitude == -6.1583261

    # Way: lat/lon in center object
    assert attractions[1].latitude == 53.4449372
    assert attractions[1].longitude == -6.1646051


@patch("backend.adapters.tour_adapter.requests.post")
def test_metrics_calculation(mock_post, adapter, mock_overpass_response):
    """Test aggregated metrics are calculated correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="donabate", radius_km=5)
    metrics = snapshot.tours

    assert metrics.total_attractions == 3
    assert metrics.free_attractions_count == 1  # Malahide Castle
    assert metrics.paid_attractions_count == 1  # Casino Museum
    assert metrics.wheelchair_accessible_count == 2  # Museum and Newbridge


@patch("backend.adapters.tour_adapter.requests.post")
def test_attractions_by_type(mock_post, adapter, mock_overpass_response):
    """Test attractions are categorized by type"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="donabate", radius_km=5)
    by_type = snapshot.tours.attractions_by_type

    assert by_type["museum"] == 1
    assert by_type["castle"] == 1
    assert by_type["park"] == 1


@patch("backend.adapters.tour_adapter.requests.post")
def test_fee_parsing(mock_post, adapter, mock_overpass_response):
    """Test fee/price field is parsed correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="donabate", radius_km=5)
    attractions = snapshot.tours.attractions

    # "fee": "yes" -> paid
    assert attractions[0].price == "yes"

    # "fee": "no" -> free
    assert attractions[1].price == "no"


@patch("backend.adapters.tour_adapter.requests.post")
def test_fetch_empty_response(mock_post, adapter):
    """Test handling of empty attractions list"""
    mock_response = Mock()
    mock_response.json.return_value = {"elements": []}
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="nowhere", radius_km=5)

    assert snapshot.tours.total_attractions == 0
    assert len(snapshot.tours.attractions) == 0
    assert snapshot.tours.free_attractions_count == 0
    assert snapshot.tours.paid_attractions_count == 0


@patch("backend.adapters.tour_adapter.requests.post")
def test_fetch_api_timeout(mock_post, adapter):
    """Test API timeout handling"""
    mock_post.side_effect = Exception("Timeout")

    with pytest.raises(Exception):
        adapter.fetch(location="donabate", radius_km=5)


@patch("backend.adapters.tour_adapter.requests.post")
def test_fetch_api_error_status(mock_post, adapter):
    """Test HTTP error handling"""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_post.return_value = mock_response

    with pytest.raises(Exception):
        adapter.fetch(location="donabate", radius_km=5)


@patch("backend.adapters.tour_adapter.requests.post")
def test_fetch_malformed_response(mock_post, adapter):
    """Test handling of malformed API response"""
    mock_response = Mock()
    mock_response.json.return_value = {"invalid": "structure"}
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    with pytest.raises(KeyError):
        adapter.fetch(location="donabate", radius_km=5)


@patch("backend.adapters.tour_adapter.requests.post")
def test_attraction_without_optional_fields(mock_post, adapter):
    """Test attraction without phone, website, opening hours"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "elements": [
            {
                "type": "node",
                "id": 123,
                "lat": 53.45,
                "lon": -6.15,
                "tags": {"name": "Simple Attraction", "tourism": "attraction"},
            }
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="test", radius_km=5)
    attraction = snapshot.tours.attractions[0]

    assert attraction.attraction_name == "Simple Attraction"
    assert attraction.phone is None
    assert attraction.website is None
    assert attraction.open_times is None


@patch("backend.adapters.tour_adapter.requests.post")
def test_different_radius_values(mock_post, adapter, mock_overpass_response):
    """Test different search radius parameters"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="donabate", radius_km=1)
    assert snapshot.location == "donabate"
    assert snapshot.tours.total_attractions == 3

    snapshot = adapter.fetch(location="donabate", radius_km=10)
    assert snapshot.tours.total_attractions == 3

    snapshot = adapter.fetch(location="donabate", radius_km=20)
    assert snapshot.tours.total_attractions == 3


@patch("backend.adapters.tour_adapter.requests.post")
def test_attraction_types_from_tags(mock_post, adapter):
    """Test different tourism types are identified correctly"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "elements": [
            {"type": "node", "id": 1, "lat": 53.45, "lon": -6.15, "tags": {"name": "Museum A", "tourism": "museum"}},
            {"type": "node", "id": 2, "lat": 53.45, "lon": -6.15, "tags": {"name": "Hotel B", "tourism": "hotel"}},
            {"type": "node", "id": 3, "lat": 53.45, "lon": -6.15, "tags": {"name": "Info C", "tourism": "information"}},
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="test", radius_km=5)
    by_type = snapshot.tours.attractions_by_type

    assert by_type.get("museum", 0) == 1
    assert by_type.get("hotel", 0) == 1
    assert by_type.get("information", 0) == 1


@patch("backend.adapters.tour_adapter.requests.post")
def test_wheelchair_accessibility_variations(mock_post, adapter):
    """Test different wheelchair accessibility values"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "elements": [
            {
                "type": "node",
                "id": 1,
                "lat": 53.45,
                "lon": -6.15,
                "tags": {"name": "A1", "tourism": "museum", "wheelchair": "yes"},
            },
            {
                "type": "node",
                "id": 2,
                "lat": 53.45,
                "lon": -6.15,
                "tags": {"name": "A2", "tourism": "museum", "wheelchair": "no"},
            },
            {
                "type": "node",
                "id": 3,
                "lat": 53.45,
                "lon": -6.15,
                "tags": {"name": "A3", "tourism": "museum", "wheelchair": "limited"},
            },
            {"type": "node", "id": 4, "lat": 53.45, "lon": -6.15, "tags": {"name": "A4", "tourism": "museum"}},
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="test", radius_km=5)

    # Only count "yes" as accessible
    assert snapshot.tours.wheelchair_accessible_count == 1


@patch("backend.adapters.tour_adapter.requests.post")
def test_location_parameter(mock_post, adapter, mock_overpass_response):
    """Test different location parameters"""
    mock_response = Mock()
    mock_response.json.return_value = mock_overpass_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    snapshot = adapter.fetch(location="malahide", radius_km=5)
    assert snapshot.location == "malahide"

    snapshot = adapter.fetch(location="dublin", radius_km=10)
    assert snapshot.location == "dublin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
