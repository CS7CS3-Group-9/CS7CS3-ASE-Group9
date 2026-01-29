import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from backend.adapters.traffic_adapter import TrafficAdapter


@pytest.fixture
def mock_traffic_response():
    """Sample response from TomTom Traffic API - full 14 incidents"""
    return {
        "location": "dublin",
        "coordinates": {
            "lat": 53.3440956,
            "lng": -6.2674862
        },
        "radius_km": 0.5,
        "total_incidents": 14,
        "summary": {
            "Jam": 13,
            "Road Closed": 1
        },
        "incidents": [
            {
                "category": "Jam",
                "severity": "Major",
                "description": "Stationary traffic",
                "from": "Chancery Street (Greek Street)",
                "to": "Mary's Lane (Greek Street)",
                "road": "Unknown road",
                "length_meters": 91.0335578732,
                "delay_seconds": 85,
                "delay_minutes": 1.4
            },
            {
                "category": "Jam",
                "severity": "Major",
                "description": "Stationary traffic",
                "from": "George's Hill (Mary's Lane)",
                "to": "Church Street (N1) (Mary's Lane)",
                "road": "Unknown road",
                "length_meters": 191.0632476919,
                "delay_seconds": 178,
                "delay_minutes": 3.0
            },
            {
                "category": "Jam",
                "severity": "Major",
                "description": "Stationary traffic",
                "from": "Lower Bridge Street (Cook Street)",
                "to": "Winetavern Street (Cook Street)",
                "road": "Unknown road",
                "length_meters": 104.9745249761,
                "delay_seconds": 112,
                "delay_minutes": 1.9
            },
            {
                "category": "Jam",
                "severity": "Major",
                "description": "Stationary traffic",
                "from": "High Street (Winetavern Street)",
                "to": "Wood Quay (Winetavern Street)",
                "road": "Unknown road",
                "length_meters": 158.488704609,
                "delay_seconds": 139,
                "delay_minutes": 2.3
            },
            {
                "category": "Jam",
                "severity": "Major",
                "description": "Stationary traffic",
                "from": "Kevin Street Lower (R110) / Kevin Street Upper (R110)",
                "to": "Patrick Street (N81) / Nicholas Street (N81)",
                "road": "Unknown road",
                "length_meters": 40.7695392422,
                "delay_seconds": 76,
                "delay_minutes": 1.3
            },
            {
                "category": "Jam",
                "severity": "Major",
                "description": "Stationary traffic",
                "from": "Upper Kevin Street (R110) (Bride Street)",
                "to": "Bride Road (Bride Street)",
                "road": "Unknown road",
                "length_meters": 205.5532124722,
                "delay_seconds": 231,
                "delay_minutes": 3.9
            },
            {
                "category": "Jam",
                "severity": "Moderate",
                "description": "Queuing traffic",
                "from": "North Circular Road (N3) (PDR6)",
                "to": "Merchant's Quay (PDR6)",
                "road": "R108, N1",
                "length_meters": 725.2961172375,
                "delay_seconds": 268,
                "delay_minutes": 4.5
            },
            {
                "category": "Jam",
                "severity": "Moderate",
                "description": "Queuing traffic",
                "from": "Long lane (N81)",
                "to": "High Street (N81)",
                "road": "N81",
                "length_meters": 688.6191833754,
                "delay_seconds": 284,
                "delay_minutes": 4.7
            },
            {
                "category": "Jam",
                "severity": "Moderate",
                "description": "Queuing traffic",
                "from": "Bride Street (Bride Road)",
                "to": "Nicholas Street (N81) (Bride Road)",
                "road": "Unknown road",
                "length_meters": 114.1159500372,
                "delay_seconds": 110,
                "delay_minutes": 1.8
            },
            {
                "category": "Jam",
                "severity": "Moderate",
                "description": "Queuing traffic",
                "from": "Parliament Street (PDR18)",
                "to": "Saint John's Road West (N4) (PDR18)",
                "road": "N4",
                "length_meters": 1120.4530749383,
                "delay_seconds": 369,
                "delay_minutes": 6.2
            },
            {
                "category": "Jam",
                "severity": "Minor",
                "description": "Slow traffic",
                "from": "Hammond Lane (Church Street)",
                "to": "King Street North (Church Street)",
                "road": "R108, N1",
                "length_meters": 411.171,
                "delay_seconds": 133,
                "delay_minutes": 2.2
            },
            {
                "category": "Jam",
                "severity": "Minor",
                "description": "Slow traffic",
                "from": "Pleasants Street (R114)",
                "to": "Great Longford Street (R114)",
                "road": "R114",
                "length_meters": 585.0126486495,
                "delay_seconds": 213,
                "delay_minutes": 3.5
            },
            {
                "category": "Jam",
                "severity": "Minor",
                "description": "Slow traffic",
                "from": "Great Longford Street (R114)",
                "to": "Dame Street (N81) (R114)",
                "road": "R114",
                "length_meters": 334.9766140326,
                "delay_seconds": 183,
                "delay_minutes": 3.0
            },
            {
                "category": "Road Closed",
                "severity": "Undefined",
                "description": "Closed",
                "from": "Exchequer Street",
                "to": "South Great George's Street (R114) / Dame Lane",
                "road": "Unknown road",
                "length_meters": 93.7069267635,
                "delay_seconds": None,
                "delay_minutes": 0
            }
        ]
    }


@pytest.fixture
def adapter():
    """Create adapter instance"""
    return TrafficAdapter()


def test_source_name(adapter):
    """Test source name returns 'traffic'"""
    assert adapter.source_name() == "traffic"


@patch('backend.adapters.traffic_adapter.requests.get')
def test_fetch_success(mock_get, adapter, mock_traffic_response):
    """Test successful API fetch and parsing"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)

    # Verify API was called
    mock_get.assert_called_once()

    # Verify snapshot structure
    assert snapshot.location == "dublin"
    assert snapshot.radius_km == 0.5
    assert snapshot.latitude == 53.3440956
    assert snapshot.longitude == -6.2674862
    assert isinstance(snapshot.timestamp, datetime)
    assert snapshot.source_status == {"tomtom": "live"}


@patch('backend.adapters.traffic_adapter.requests.get')
def test_incident_parsing(mock_get, adapter, mock_traffic_response):
    """Test individual incidents are parsed correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    incidents = snapshot.metrics.incidents

    # Should have 14 incidents
    assert len(incidents) == 14

    # Check first incident (Major Jam)
    incident = incidents[0]
    assert incident.category == "Jam"
    assert incident.severity == "Major"
    assert incident.description == "Stationary traffic"
    assert incident.from_location == "Chancery Street (Greek Street)"
    assert incident.to_location == "Mary's Lane (Greek Street)"
    assert incident.road == "Unknown road"
    assert incident.length_meters == 91.0335578732
    assert incident.delay_seconds == 85
    assert incident.delay_minutes == 1.4


@patch('backend.adapters.traffic_adapter.requests.get')
def test_metrics_calculation(mock_get, adapter, mock_traffic_response):
    """Test aggregated metrics are calculated correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    metrics = snapshot.metrics

    assert metrics.total_incidents == 14


@patch('backend.adapters.traffic_adapter.requests.get')
def test_incidents_by_category(mock_get, adapter, mock_traffic_response):
    """Test incidents are grouped by category"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    by_category = snapshot.metrics.incidents_by_category

    assert by_category["Jam"] == 13
    assert by_category["Road Closed"] == 1


@patch('backend.adapters.traffic_adapter.requests.get')
def test_incidents_by_severity(mock_get, adapter, mock_traffic_response):
    """Test incidents are grouped by severity"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    by_severity = snapshot.metrics.incidents_by_severity

    assert by_severity["Major"] == 6
    assert by_severity["Moderate"] == 4
    assert by_severity["Minor"] == 3
    assert by_severity["Undefined"] == 1


@patch('backend.adapters.traffic_adapter.requests.get')
def test_total_delay_calculation(mock_get, adapter, mock_traffic_response):
    """Test total delay is calculated correctly"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    
    # Total delay: 1.4 + 3.0 + 1.9 + 2.3 + 1.3 + 3.9 + 4.5 + 4.7 + 1.8 + 6.2 + 2.2 + 3.5 + 3.0 + 0 = 39.7 minutes
    assert snapshot.metrics.total_delay_minutes == pytest.approx(39.7, 0.1)


@patch('backend.adapters.traffic_adapter.requests.get')
def test_average_delay_calculation(mock_get, adapter, mock_traffic_response):
    """Test average delay per incident calculation"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    
    # Average delay = 39.7 total / 14 incidents = 2.836 minutes per incident
    assert snapshot.metrics.average_delay_minutes == pytest.approx(2.836, 0.01)


@patch('backend.adapters.traffic_adapter.requests.get')
def test_congestion_level_high(mock_get, adapter, mock_traffic_response):
    """Test congestion level is calculated as 'high' with many incidents"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    
    # With 14 incidents in 0.5km radius (28 per km), congestion should be high
    assert snapshot.metrics.congestion_level == "high"


@patch('backend.adapters.traffic_adapter.requests.get')
def test_congestion_level_low(mock_get, adapter):
    """Test congestion level is 'low' with few incidents"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "location": "rural",
        "coordinates": {"lat": 53.0, "lng": -6.0},
        "radius_km": 5,
        "total_incidents": 1,
        "summary": {"Jam": 1},
        "incidents": [
            {
                "category": "Jam",
                "severity": "Minor",
                "description": "Slow traffic",
                "from": "A",
                "to": "B",
                "road": "R123",
                "length_meters": 100,
                "delay_seconds": 30,
                "delay_minutes": 0.5
            }
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="rural", radius_km=5)
    
    # With 1 incident in 5km radius, congestion should be low
    assert snapshot.metrics.congestion_level == "low"


@patch('backend.adapters.traffic_adapter.requests.get')
def test_fetch_empty_response(mock_get, adapter):
    """Test handling of no incidents"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "location": "quiet_area",
        "coordinates": {"lat": 53.0, "lng": -6.0},
        "radius_km": 5,
        "total_incidents": 0,
        "summary": {},
        "incidents": []
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="quiet_area", radius_km=5)

    assert snapshot.metrics.total_incidents == 0
    assert len(snapshot.metrics.incidents) == 0
    assert snapshot.metrics.total_delay_minutes == 0
    assert snapshot.metrics.congestion_level == "low"


@patch('backend.adapters.traffic_adapter.requests.get')
def test_fetch_api_timeout(mock_get, adapter):
    """Test API timeout handling"""
    mock_get.side_effect = Exception("Timeout")

    with pytest.raises(Exception):
        adapter.fetch(location="dublin", radius_km=0.5)


@patch('backend.adapters.traffic_adapter.requests.get')
def test_fetch_api_error_status(mock_get, adapter):
    """Test HTTP error handling"""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_get.return_value = mock_response

    with pytest.raises(Exception):
        adapter.fetch(location="dublin", radius_km=0.5)


@patch('backend.adapters.traffic_adapter.requests.get')
def test_fetch_malformed_response(mock_get, adapter):
    """Test handling of malformed API response"""
    mock_response = Mock()
    mock_response.json.return_value = {"invalid": "structure"}
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    with pytest.raises(KeyError):
        adapter.fetch(location="dublin", radius_km=0.5)


@patch('backend.adapters.traffic_adapter.requests.get')
def test_null_delay_handling(mock_get, adapter):
    """Test handling of null delay values (like road closures)"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "location": "test",
        "coordinates": {"lat": 53.0, "lng": -6.0},
        "radius_km": 1,
        "total_incidents": 1,
        "summary": {"Road Closed": 1},
        "incidents": [
            {
                "category": "Road Closed",
                "severity": "Undefined",
                "description": "Closed",
                "from": "A",
                "to": "B",
                "road": "R123",
                "length_meters": 100,
                "delay_seconds": None,
                "delay_minutes": 0
            }
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    snapshot = adapter.fetch(location="test", radius_km=1)
    
    incident = snapshot.metrics.incidents[0]
    assert incident.delay_seconds is None
    assert incident.delay_minutes == 0


@patch('backend.adapters.traffic_adapter.requests.get')
def test_different_radius_values(mock_get, adapter, mock_traffic_response):
    """Test different search radius parameters"""
    mock_response = Mock()
    mock_response.json.return_value = mock_traffic_response
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Test with different radius values
    snapshot = adapter.fetch(location="dublin", radius_km=0.5)
    assert snapshot.radius_km == 0.5

    snapshot = adapter.fetch(location="dublin", radius_km=1.0)
    assert snapshot.radius_km == 1.0

    snapshot = adapter.fetch(location="dublin", radius_km=5.0)
    assert snapshot.radius_km == 5.0


@patch('backend.adapters.traffic_adapter.requests.get')
def test_location_parameter(mock_get, adapter):
    """Test different location parameters"""
    # First location: cork
    mock_response_cork = Mock()
    mock_response_cork.json.return_value = {
        "location": "cork",
        "coordinates": {"lat": 51.89, "lng": -8.47},
        "radius_km": 1,
        "total_incidents": 0,
        "summary": {},
        "incidents": []
    }
    mock_response_cork.raise_for_status = Mock()
    mock_get.return_value = mock_response_cork

    snapshot = adapter.fetch(location="cork", radius_km=1)
    assert snapshot.location == "cork"

    # Second location: galway
    mock_response_galway = Mock()
    mock_response_galway.json.return_value = {
        "location": "galway",
        "coordinates": {"lat": 53.27, "lng": -9.05},
        "radius_km": 1,
        "total_incidents": 0,
        "summary": {},
        "incidents": []
    }
    mock_response_galway.raise_for_status = Mock()
    mock_get.return_value = mock_response_galway

    snapshot = adapter.fetch(location="galway", radius_km=1)
    assert snapshot.location == "galway"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])