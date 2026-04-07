import pytest
from unittest.mock import Mock, patch
from backend.adapters.bike_stations_adapter import BikeStationsAdapter


@pytest.fixture
def mock_api_response():
    """Sample response from Dublin Bikes API"""
    return {
        "network": {
            "stations": [
                {
                    "name": "Smithfield",
                    "latitude": 53.3478,
                    "longitude": -6.2784,
                    "free_bikes": 12,
                    "empty_slots": 8,
                    "extra": {"slots": 20},
                },
                {
                    "name": "Parnell Square North",
                    "latitude": 53.3535,
                    "longitude": -6.2588,
                    "free_bikes": 5,
                    "empty_slots": 15,
                    "extra": {"slots": 20},
                },
            ]
        }
    }


@pytest.fixture
def adapter():
    """Create adapter instance"""
    return BikeStationsAdapter()


def test_source_name(adapter):
    """Test source name returns 'bikes_stations'"""
    assert adapter.source_name() == "bikes_stations"


@patch("backend.adapters.bike_stations_adapter.requests.get")
def test_fetch_success(mock_get, adapter, mock_api_response):
    """Test successful API fetch and parsing"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    stations = adapter.fetch(location="dublin")

    mock_get.assert_called_once_with("https://api.citybik.es/v2/networks/dublinbikes", timeout=5)

    assert len(stations) == 2
    assert stations[0]["name"] == "Smithfield"
    assert stations[0]["lat"] == 53.3478
    assert stations[0]["lon"] == -6.2784
    assert stations[0]["free_bikes"] == 12
    assert stations[0]["empty_slots"] == 8
    assert stations[0]["total"] == 20


@patch("backend.adapters.bike_stations_adapter.requests.get")
def test_fetch_empty_response(mock_get, adapter):
    """Test handling of empty stations list"""
    mock_response = Mock()
    mock_response.json.return_value = {"network": {"stations": []}}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    stations = adapter.fetch()

    assert stations == []


@patch("backend.adapters.bike_stations_adapter.requests.get")
def test_fetch_api_timeout(mock_get, adapter):
    """Test API timeout handling"""
    mock_get.side_effect = Exception("Timeout")

    with pytest.raises(Exception):
        adapter.fetch()


@patch("backend.adapters.bike_stations_adapter.requests.get")
def test_fetch_api_error_status(mock_get, adapter):
    """Test HTTP error handling"""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_get.return_value = mock_response

    with pytest.raises(Exception):
        adapter.fetch()


@patch("backend.adapters.bike_stations_adapter.requests.get")
def test_fetch_malformed_response(mock_get, adapter):
    """Test handling of malformed API response"""
    mock_response = Mock()
    mock_response.json.return_value = {"invalid": "structure"}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    with pytest.raises(KeyError):
        adapter.fetch()


@patch("backend.adapters.bike_stations_adapter.requests.get")
def test_fetch_location_parameter(mock_get, adapter, mock_api_response):
    """Test different location parameters"""
    mock_response = Mock()
    mock_response.json.return_value = mock_api_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Test with custom location
    stations = adapter.fetch(location="dublin_north")
    # Location is not used in the adapter, but the parameter is accepted

    # Test default location
    stations = adapter.fetch()
    assert len(stations) == 2


@patch.dict("os.environ", {"FORCE_BIKES_PREDICTION": "1"})
def test_fetch_force_prediction():
    """Test forced prediction raises RuntimeError"""
    adapter = BikeStationsAdapter()
    with pytest.raises(RuntimeError, match="Forced bikes station prediction"):
        adapter.fetch()
