import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from backend.adapters.airquality_adapter import AirQualityAdapter


@pytest.fixture
def mock_airquality_response():
    """Sample response from Open-Meteo Air Quality API"""
    return {
        "latitude": 53.300003,
        "longitude": -6.299999,
        "generationtime_ms": 0.2830028533935547,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 11.0,
        "current_units": {
            "time": "iso8601",
            "interval": "seconds",
            "pm2_5": "μg/m³",
            "pm10": "μg/m³",
            "nitrogen_dioxide": "μg/m³",
            "carbon_monoxide": "μg/m³",
            "ozone": "μg/m³",
            "sulphur_dioxide": "μg/m³",
            "european_aqi": "EAQI",
        },
        "current": {
            "time": "2026-01-29T16:00",
            "interval": 3600,
            "pm2_5": 4.1,
            "pm10": 9.9,
            "nitrogen_dioxide": 7.6,
            "carbon_monoxide": 153.0,
            "ozone": 61.0,
            "sulphur_dioxide": 0.7,
            "european_aqi": 24,
        },
    }


@pytest.fixture
def adapter():
    """Create adapter instance"""
    return AirQualityAdapter()


def test_source_name(adapter):
    """Test source name returns 'airquality'"""
    assert adapter.source_name() == "airquality"


@patch("backend.adapters.airquality_adapter.requests.get")
def test_fetch_success(mock_get, adapter, mock_airquality_response):
    """Test successful API fetch and parsing"""
    mock_response = Mock()
    mock_response.json.return_value = mock_airquality_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(latitude=53.3, longitude=-6.3)

    # Verify API was called
    mock_get.assert_called_once()

    # Verify snapshot structure
    assert snapshot.latitude == 53.300003
    assert snapshot.longitude == -6.299999
    assert snapshot.elevation == 11.0
    assert snapshot.timezone == "GMT"
    assert isinstance(snapshot.timestamp, datetime)
    assert snapshot.source_status == {"open-meteo": "live"}


@patch("backend.adapters.airquality_adapter.requests.get")
def test_pollutant_parsing(mock_get, adapter, mock_airquality_response):
    """Test individual pollutants are parsed correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_airquality_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(latitude=53.3, longitude=-6.3)
    pollutants = snapshot.metrics.pollutants

    # Check all pollutant values
    assert pollutants.pm2_5 == 4.1
    assert pollutants.pm10 == 9.9
    assert pollutants.nitrogen_dioxide == 7.6
    assert pollutants.carbon_monoxide == 153.0
    assert pollutants.ozone == 61.0
    assert pollutants.sulphur_dioxide == 0.7


@patch("backend.adapters.airquality_adapter.requests.get")
def test_pollutant_units(mock_get, adapter, mock_airquality_response):
    """Test pollutant units are stored correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_airquality_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(latitude=53.3, longitude=-6.3)
    units = snapshot.metrics.pollutants.units

    assert units["pm2_5"] == "μg/m³"
    assert units["pm10"] == "μg/m³"
    assert units["carbon_monoxide"] == "μg/m³"
    assert units["ozone"] == "μg/m³"


@patch("backend.adapters.airquality_adapter.requests.get")
def test_aqi_value(mock_get, adapter, mock_airquality_response):
    """Test AQI value is extracted correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_airquality_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(latitude=53.3, longitude=-6.3)

    assert snapshot.metrics.aqi_value == 24


@patch("backend.adapters.airquality_adapter.requests.get")
def test_different_coordinates(mock_get, adapter, mock_airquality_response):
    """Test different latitude/longitude parameters"""
    mock_response = Mock()
    mock_response.json.return_value = mock_airquality_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Dublin
    snapshot = adapter.fetch(latitude=53.3498, longitude=-6.2603)
    assert snapshot.latitude == 53.300003
    assert snapshot.longitude == -6.299999

    # Cork
    snapshot = adapter.fetch(latitude=51.8969, longitude=-8.4863)
    assert snapshot.latitude == 53.300003  # Mock returns same data


@patch("backend.adapters.airquality_adapter.requests.get")
def test_fetch_api_timeout(mock_get, adapter):
    """Test API timeout handling"""
    mock_get.side_effect = Exception("Timeout")

    with pytest.raises(Exception):
        adapter.fetch(latitude=53.3, longitude=-6.3)


@patch("backend.adapters.airquality_adapter.requests.get")
def test_fetch_api_error_status(mock_get, adapter):
    """Test HTTP error handling"""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_get.return_value = mock_response

    with pytest.raises(Exception):
        adapter.fetch(latitude=53.3, longitude=-6.3)


@patch("backend.adapters.airquality_adapter.requests.get")
def test_fetch_malformed_response(mock_get, adapter):
    """Test handling of malformed API response"""
    mock_response = Mock()
    mock_response.json.return_value = {"invalid": "structure"}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    with pytest.raises(KeyError):
        adapter.fetch(latitude=53.3, longitude=-6.3)


@patch("backend.adapters.airquality_adapter.requests.get")
def test_timestamp_parsing(mock_get, adapter, mock_airquality_response):
    """Test timestamp is parsed correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_airquality_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(latitude=53.3, longitude=-6.3)

    assert isinstance(snapshot.timestamp, datetime)
    assert snapshot.timestamp.year == 2026
    assert snapshot.timestamp.month == 1
    assert snapshot.timestamp.day == 29


@patch("backend.adapters.airquality_adapter.requests.get")
def test_zero_pollutants(mock_get, adapter):
    """Test handling of zero pollutant values"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "latitude": 53.3,
        "longitude": -6.3,
        "elevation": 10.0,
        "timezone": "GMT",
        "current_units": {
            "pm2_5": "μg/m³",
            "pm10": "μg/m³",
            "nitrogen_dioxide": "μg/m³",
            "carbon_monoxide": "μg/m³",
            "ozone": "μg/m³",
            "sulphur_dioxide": "μg/m³",
        },
        "current": {
            "time": "2026-01-29T16:00",
            "pm2_5": 0.0,
            "pm10": 0.0,
            "nitrogen_dioxide": 0.0,
            "carbon_monoxide": 0.0,
            "ozone": 0.0,
            "sulphur_dioxide": 0.0,
            "european_aqi": 0,
        },
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(latitude=53.3, longitude=-6.3)

    assert snapshot.metrics.aqi_value == 0
    assert all(
        getattr(snapshot.metrics.pollutants, attr) == 0.0
        for attr in [
            "pm2_5",
            "pm10",
            "nitrogen_dioxide",
            "carbon_monoxide",
            "ozone",
            "sulphur_dioxide",
        ]
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
