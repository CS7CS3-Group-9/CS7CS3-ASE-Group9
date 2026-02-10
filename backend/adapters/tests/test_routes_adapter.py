import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from backend.adapters.routes_adapter import RoutesAdapter


@pytest.fixture
def mock_api_response():
    """Sample response from Google Routes API"""
    return {
        "origin": {
            "input": "donabate",
            "coordinates": {"lat": 53.4853365, "lng": -6.1504482},
        },
        "destination": {
            "input": "portrane",
            "coordinates": {"lat": 53.49319999999999, "lng": -6.11462},
        },
        "distance_meters": 2823,
        "duration": "278s",
        "encoded_polyline": (
            "_jmeIhgpd@CmBGa@qAqBo@q@y@a@gBm@c@KoEk@_@WWg@Qs@g@cEw@gHOgBq@wF"
            "Oq@aC}G}@uBiEyHaDcF_@iAYaBOyAO{CAyBFwHNsB?eA}@qPAeAHsAh@uAsAcE"
            "eAuHM}EWuLiAm_@AyAFgAn@gEj@qCNyAB{B"
        ),
    }


@pytest.fixture
def adapter():
    """Create adapter instance"""
    return RoutesAdapter()


def test_source_name(adapter):
    """Test source name returns 'routes'"""
    assert adapter.source_name() == "routes"


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_success(mock_post, adapter, mock_api_response):
    """Test successful API fetch and parsing"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="donabate", end="portrane")

    # Verify API was called
    mock_post.assert_called_once()

    # Verify route recommendation structure
    assert recommendation.start == "donabate"
    assert recommendation.end == "portrane"
    assert recommendation.duration == "278s"
    assert isinstance(recommendation.route, str)
    POLYLINE = (
        "_jmeIhgpd@CmBGa@qAqBo@q@y@a@gBm@c@KoEk@_@WWg@Qs@g@cEw@gHOgBq@wF"
        "Oq@aC}G}@uBiEyHaDcF_@iAYaBOyAO{CAyBFwHNsB?eA}@qPAeAHsAh@uAsAcE"
        "eAuHM}EWuLiAm_@AyAFgAn@gEj@qCNyAB{B"
    )
    assert recommendation.route == POLYLINE


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_origin_coordinates(mock_post, adapter, mock_api_response):
    """Test origin coordinates are correctly extracted"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="donabate", end="portrane")

    assert hasattr(recommendation, "origin_lat")
    assert hasattr(recommendation, "origin_lng")
    assert recommendation.origin_lat == 53.4853365
    assert recommendation.origin_lng == -6.1504482


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_destination_coordinates(mock_post, adapter, mock_api_response):
    """Test destination coordinates are correctly extracted"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="donabate", end="portrane")

    assert hasattr(recommendation, "dest_lat")
    assert hasattr(recommendation, "dest_lng")
    assert recommendation.dest_lat == 53.49319999999999
    assert recommendation.dest_lng == -6.11462


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_distance(mock_post, adapter, mock_api_response):
    """Test distance is correctly extracted"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="donabate", end="portrane")

    assert hasattr(recommendation, "distance_meters")
    assert recommendation.distance_meters == 2823


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_transport_mode(mock_post, adapter, mock_api_response):
    """Test transport mode parameter"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    # Test with different transport modes
    recommendation = adapter.fetch(start="donabate", end="portrane", transport_mode="DRIVE")
    assert recommendation.transport_mode == "DRIVE"

    recommendation = adapter.fetch(start="donabate", end="portrane", transport_mode="WALK")
    assert recommendation.transport_mode == "WALK"

    recommendation = adapter.fetch(start="donabate", end="portrane", transport_mode="BICYCLE")
    assert recommendation.transport_mode == "BICYCLE"


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_route_preference(mock_post, adapter, mock_api_response):
    """Test route preference (fast vs eco)"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    # Test fast route
    recommendation = adapter.fetch(start="donabate", end="portrane", fast_route=True)
    assert recommendation.fast_route is True
    assert recommendation.eco_route is False

    # Test eco route
    recommendation = adapter.fetch(start="donabate", end="portrane", eco_route=True)
    assert recommendation.eco_route is True
    assert recommendation.fast_route is False


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_with_departure_time(mock_post, adapter, mock_api_response):
    """Test route with departure time"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    dep_time = datetime.now()
    recommendation = adapter.fetch(start="donabate", end="portrane", dep_time=dep_time)

    assert recommendation.dep_time == dep_time
    assert recommendation.arr_time is None


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_with_arrival_time(mock_post, adapter, mock_api_response):
    """Test route with arrival time"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    arr_time = datetime.now()
    recommendation = adapter.fetch(start="donabate", end="portrane", arr_time=arr_time)

    assert recommendation.arr_time == arr_time
    assert recommendation.dep_time is None


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_api_timeout(mock_post, adapter):
    """Test API timeout handling"""
    mock_post.side_effect = Exception("Timeout")

    with pytest.raises(Exception):
        adapter.fetch(start="donabate", end="portrane")


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_api_error_status(mock_post, adapter):
    """Test HTTP error handling"""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_post.return_value = mock_response

    with pytest.raises(Exception):
        adapter.fetch(start="donabate", end="portrane")


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_malformed_response(mock_post, adapter):
    """Test handling of malformed API response"""
    mock_response = Mock()
    mock_response.json.return_value = {"invalid": "structure"}
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    with pytest.raises(KeyError):
        adapter.fetch(start="donabate", end="portrane")


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_missing_polyline(mock_post, adapter):
    """Test handling when polyline is missing"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "origin": {"input": "donabate", "coordinates": {"lat": 53.48, "lng": -6.15}},
        "destination": {
            "input": "portrane",
            "coordinates": {"lat": 53.49, "lng": -6.11},
        },
        "distance_meters": 2823,
        "duration": "278s",
        # Missing encoded_polyline
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="donabate", end="portrane")

    # Should handle missing polyline gracefully
    assert recommendation.route is None or recommendation.route == ""


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_duration_parsing(mock_post, adapter, mock_api_response):
    """Test duration is parsed correctly from '278s' format"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="donabate", end="portrane")

    # Duration should be extracted as string or converted to integer
    assert recommendation.duration in ["278s", 278]


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_invalid_transport_mode(mock_post, adapter):
    """Test handling of invalid transport mode"""
    mock_post.side_effect = Exception("Invalid transport mode")

    with pytest.raises(Exception):
        adapter.fetch(start="donabate", end="portrane", transport_mode="INVALID")


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_both_times_specified(mock_post, adapter):
    """Test that only one of dep_time or arr_time can be specified"""
    # Should raise error or handle gracefully
    with pytest.raises(ValueError):
        adapter.fetch(
            start="donabate",
            end="portrane",
            dep_time=datetime.now(),
            arr_time=datetime.now(),
        )


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_both_route_preferences(mock_post, adapter):
    """Test that both fast_route and eco_route cannot be True"""
    # Should raise error or handle gracefully
    with pytest.raises(ValueError):
        adapter.fetch(start="donabate", end="portrane", fast_route=True, eco_route=True)


@pytest.fixture
def mock_multistop_response():
    """Sample response for multi-stop route"""
    return {
        "optimal_route_order": ["swords", "donabate", "portrane"],
        "total_duration_seconds": 1278,
        "total_duration_formatted": "21m",
        "total_distance_km": 10.4,
        "number_of_stops": 3,
        "legs": [
            {
                "from": "swords",
                "to": "donabate",
                "duration_seconds": 979,
                "duration_formatted": "16m",
                "distance_meters": 7532,
                "distance_km": 7.5,
            },
            {
                "from": "donabate",
                "to": "portrane",
                "duration_seconds": 299,
                "duration_formatted": "4m",
                "distance_meters": 2823,
                "distance_km": 2.8,
            },
        ],
    }


@patch("backend.adapters.routes_adapter.requests.post")
def test_fetch_multistop_route(mock_post, adapter, mock_multistop_response):
    """Test fetching route with multiple stops"""
    mock_response = Mock()
    mock_response.json.return_value = mock_multistop_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    # Verify it's recognized as multi-stop
    assert recommendation.is_multi_stop() is True
    assert recommendation.waypoints == ["donabate"]


@patch("backend.adapters.routes_adapter.requests.post")
def test_multistop_route_order(mock_post, adapter, mock_multistop_response):
    """Test optimal route order is extracted"""
    mock_response = Mock()
    mock_response.json.return_value = mock_multistop_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    assert recommendation.multi_stop_data.optimal_route_order == [
        "swords",
        "donabate",
        "portrane",
    ]
    assert recommendation.multi_stop_data.number_of_stops == 3


@patch("backend.adapters.routes_adapter.requests.post")
def test_multistop_total_metrics(mock_post, adapter, mock_multistop_response):
    """Test total duration and distance for multi-stop route"""
    mock_response = Mock()
    mock_response.json.return_value = mock_multistop_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    assert recommendation.multi_stop_data.total_duration_seconds == 1278
    assert recommendation.multi_stop_data.total_duration_formatted == "21m"
    assert recommendation.multi_stop_data.total_distance_km == 10.4


@patch("backend.adapters.routes_adapter.requests.post")
def test_multistop_legs(mock_post, adapter, mock_multistop_response):
    """Test route legs are parsed correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_multistop_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    legs = recommendation.multi_stop_data.legs
    assert len(legs) == 2

    # First leg: swords -> donabate
    assert legs[0].from_location == "swords"
    assert legs[0].to_location == "donabate"
    assert legs[0].duration_seconds == 979
    assert legs[0].distance_km == 7.5

    # Second leg: donabate -> portrane
    assert legs[1].from_location == "donabate"
    assert legs[1].to_location == "portrane"
    assert legs[1].duration_seconds == 299
    assert legs[1].distance_km == 2.8


@patch("backend.adapters.routes_adapter.requests.post")
def test_multistop_with_multiple_waypoints(mock_post, adapter):
    """Test route with multiple waypoints"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "optimal_route_order": ["A", "B", "C", "D"],
        "total_duration_seconds": 2000,
        "total_duration_formatted": "33m",
        "total_distance_km": 15.5,
        "number_of_stops": 4,
        "legs": [
            {
                "from": "A",
                "to": "B",
                "duration_seconds": 600,
                "duration_formatted": "10m",
                "distance_meters": 5000,
                "distance_km": 5.0,
            },
            {
                "from": "B",
                "to": "C",
                "duration_seconds": 700,
                "duration_formatted": "11m",
                "distance_meters": 5500,
                "distance_km": 5.5,
            },
            {
                "from": "C",
                "to": "D",
                "duration_seconds": 700,
                "duration_formatted": "11m",
                "distance_meters": 5000,
                "distance_km": 5.0,
            },
        ],
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="A", end="D", waypoints=["B", "C"])

    assert len(recommendation.waypoints) == 2
    assert recommendation.multi_stop_data.number_of_stops == 4
    assert len(recommendation.multi_stop_data.legs) == 3


@patch("backend.adapters.routes_adapter.requests.post")
def test_multistop_duration_sum(mock_post, adapter, mock_multistop_response):
    """Test that leg durations sum to total duration"""
    mock_response = Mock()
    mock_response.json.return_value = mock_multistop_response
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    legs = recommendation.multi_stop_data.legs
    total_leg_duration = sum(leg.duration_seconds for leg in legs)

    assert total_leg_duration == 979 + 299
    assert total_leg_duration == 1278
    assert total_leg_duration == recommendation.multi_stop_data.total_duration_seconds


@patch("backend.adapters.routes_adapter.requests.post")
def test_single_stop_is_not_multistop(mock_post, adapter):
    """Test that route without waypoints is not multi-stop"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "origin": {"input": "A", "coordinates": {"lat": 53.48, "lng": -6.15}},
        "destination": {"input": "B", "coordinates": {"lat": 53.49, "lng": -6.11}},
        "distance_meters": 2823,
        "duration": "278s",
        "encoded_polyline": "abc123",
    }
    mock_response.raise_for_status = Mock()
    mock_post.return_value = mock_response

    recommendation = adapter.fetch(start="A", end="B")

    assert recommendation.is_multi_stop() is False
    assert len(recommendation.waypoints) == 0
    assert recommendation.multi_stop_data is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
