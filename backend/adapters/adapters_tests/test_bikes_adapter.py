import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from backend.adapters.bikes_adapter import BikesAdapter


@pytest.fixture
def mock_api_response():
    """Sample response from Dublin Bikes API"""
    return {
        "network": {
            "stations": [
                {
                    "name": "Smithfield",
                    "free_bikes": 12,
                    "empty_slots": 8,
                    "extra": {"slots": 20}
                },
                {
                    "name": "Parnell Square North",
                    "free_bikes": 5,
                    "empty_slots": 15,
                    "extra": {"slots": 20}
                },
                {
                    "name": "Custom House",
                    "free_bikes": 0,
                    "empty_slots": 30,
                    "extra": {"slots": 30}
                }
            ]
        }
    }


@pytest.fixture
def adapter():
    """Create adapter instance"""
    return BikesAdapter()


def test_source_name(adapter):
    """Test source name returns 'bikes'"""
    assert adapter.source_name() == "bikes"


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_success(mock_get, adapter, mock_api_response):
    """Test successful API fetch and parsing"""
    # Mock the API response
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Fetch data
    snapshot = adapter.fetch(location="dublin")

    # Verify API was called correctly
    mock_get.assert_called_once_with(
        "https://api.citybik.es/v2/networks/dublinbikes",
        timeout=5
    )

    # Verify snapshot structure
    assert snapshot.location == "dublin"
    assert snapshot.source_status == {"bikes": "live"}
    assert isinstance(snapshot.timestamp, datetime)

    # Verify bike metrics are calculated correctly
    assert snapshot.bikes.available_bikes == 17  # 12 + 5 + 0
    assert snapshot.bikes.available_docks == 53  # 8 + 15 + 30
    assert snapshot.bikes.stations_reporting == 3


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_station_parsing(mock_get, adapter, mock_api_response):
    """Test individual station metrics are parsed correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch()

    # Verify we can access station data through the snapshot
    assert snapshot.bikes.stations_reporting == 3


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_empty_response(mock_get, adapter):
    """Test handling of empty stations list"""
    mock_response = Mock()
    mock_response.json.return_value = {"network": {"stations": []}}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch()

    assert snapshot.bikes.available_bikes == 0
    assert snapshot.bikes.available_docks == 0
    assert snapshot.bikes.stations_reporting == 0


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_api_timeout(mock_get, adapter):
    """Test API timeout handling"""
    mock_get.side_effect = Exception("Timeout")

    with pytest.raises(Exception):
        adapter.fetch()


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_api_error_status(mock_get, adapter):
    """Test HTTP error handling"""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_get.return_value = mock_response

    with pytest.raises(Exception):
        adapter.fetch()


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_malformed_response(mock_get, adapter):
    """Test handling of malformed API response"""
    mock_response = Mock()
    mock_response.json.return_value = {"invalid": "structure"}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    with pytest.raises(KeyError):
        adapter.fetch()


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_location_parameter(mock_get, adapter, mock_api_response):
    """Test different location parameters"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Test with custom location
    snapshot = adapter.fetch(location="dublin_north")
    assert snapshot.location == "dublin_north"

    # Test default location
    snapshot = adapter.fetch()
    assert snapshot.location == "dublin"


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_all_stations_have_bikes(mock_get, adapter):
    """Test when all stations have bikes available"""
    response_data = {
        "network": {
            "stations": [
                {"name": "Station A", "free_bikes": 10, "empty_slots": 5, "extra": {"slots": 15}},
                {"name": "Station B", "free_bikes": 20, "empty_slots": 10, "extra": {"slots": 30}}
            ]
        }
    }
    
    mock_response = Mock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch()

    assert snapshot.bikes.available_bikes == 30
    assert snapshot.bikes.available_docks == 15
    assert snapshot.bikes.stations_reporting == 2


@patch('backend.adapters.bikes_adapter.requests.get')
def test_fetch_no_bikes_available(mock_get, adapter):
    """Test when no bikes are available at any station"""
    response_data = {
        "network": {
            "stations": [
                {"name": "Station A", "free_bikes": 0, "empty_slots": 15, "extra": {"slots": 15}},
                {"name": "Station B", "free_bikes": 0, "empty_slots": 30, "extra": {"slots": 30}}
            ]
        }
    }
    
    mock_response = Mock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch()

    assert snapshot.bikes.available_bikes == 0
    assert snapshot.bikes.available_docks == 45


@patch('backend.adapters.bikes_adapter.requests.get')
def test_timestamp_is_current(mock_get, adapter, mock_api_response):
    """Test that timestamp is set to current UTC time"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    before = datetime.utcnow()
    snapshot = adapter.fetch()
    after = datetime.utcnow()

    assert before <= snapshot.timestamp <= after


if __name__ == "__main__":
    pytest.main([__file__, "-v"])