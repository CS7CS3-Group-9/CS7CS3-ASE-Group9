"""
Tests for GET /health endpoint.

TDD - tests for backend/api/endpoints/health.py
Run: pytest backend/api/tests/test_health.py -v
"""
import pytest
from unittest.mock import patch
from flask import Flask

from backend.api.endpoints.health import health_bp, ADAPTER_REGISTRY


@pytest.fixture
def app():
    """Create a Flask app with the health blueprint registered."""
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


def _mock_all_configured(adapter_path):
    """Helper - pretend every adapter is importable."""
    return 'configured'


# ──────────────────────────────────────────────
# 1. Basic endpoint tests
# ──────────────────────────────────────────────

@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_returns_200(mock_check, client):
    """Health endpoint should return 200 OK."""
    response = client.get('/health')
    assert response.status_code == 200


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_returns_json(mock_check, client):
    """Health endpoint should return JSON content type."""
    response = client.get('/health')
    assert response.content_type == 'application/json'


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_status_ok(mock_check, client):
    """Health endpoint should return status = ok."""
    response = client.get('/health')
    data = response.get_json()
    assert data['status'] == 'ok'


# ──────────────────────────────────────────────
# 2. Adapter listing tests
# ──────────────────────────────────────────────

@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_contains_adapters_key(mock_check, client):
    """Response should contain an 'adapters' key."""
    response = client.get('/health')
    data = response.get_json()
    assert 'adapters' in data


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_adapters_is_dict(mock_check, client):
    """Adapters should be a dictionary of adapter_name: status."""
    response = client.get('/health')
    data = response.get_json()
    assert isinstance(data['adapters'], dict)


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_lists_known_adapters(mock_check, client):
    """Should list the adapters that are configured in the system."""
    response = client.get('/health')
    data = response.get_json()
    adapters = data['adapters']

    expected_adapters = ['bikes', 'routes', 'traffic', 'air_quality', 'tour']

    for adapter_name in expected_adapters:
        assert adapter_name in adapters, (
            f"Expected adapter '{adapter_name}' in health response"
        )


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_adapter_status_values(mock_check, client):
    """Each adapter should have a valid status string."""
    response = client.get('/health')
    data = response.get_json()
    adapters = data['adapters']

    for name, status in adapters.items():
        assert isinstance(status, str), (
            f"Adapter '{name}' status should be a string, got {type(status)}"
        )
        assert status in ('configured', 'unavailable', 'error'), (
            f"Adapter '{name}' has unexpected status: {status}"
        )


def test_health_adapter_unavailable_when_import_fails(client):
    """Adapter should show 'unavailable' when it can't be imported."""
    def _mock_one_fails(adapter_path):
        if 'bikes' in adapter_path:
            return 'unavailable'
        return 'configured'

    with patch('backend.api.endpoints.health._check_adapter_status',
               side_effect=_mock_one_fails):
        response = client.get('/health')
        data = response.get_json()
        assert data['adapters']['bikes'] == 'unavailable'
        assert data['adapters']['routes'] == 'configured'


# ──────────────────────────────────────────────
# 3. Timestamp / caching tests
# ──────────────────────────────────────────────

@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_contains_timestamp(mock_check, client):
    """Response should include a timestamp field."""
    response = client.get('/health')
    data = response.get_json()
    assert 'timestamp' in data


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_timestamp_is_string(mock_check, client):
    """Timestamp should be an ISO format string."""
    response = client.get('/health')
    data = response.get_json()
    assert isinstance(data['timestamp'], str)
    assert 'T' in data['timestamp']


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_contains_last_snapshot(mock_check, client):
    """Response should include last_snapshot field."""
    response = client.get('/health')
    data = response.get_json()
    assert 'last_snapshot' in data


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_last_snapshot_default_null(mock_check, client):
    """last_snapshot should be null when no caching has occurred."""
    response = client.get('/health')
    data = response.get_json()
    assert data['last_snapshot'] is None


# ──────────────────────────────────────────────
# 4. Edge cases
# ──────────────────────────────────────────────

def test_health_post_not_allowed(client):
    """POST to /health should return 405 Method Not Allowed."""
    response = client.post('/health')
    assert response.status_code == 405


@patch('backend.api.endpoints.health._check_adapter_status',
       side_effect=_mock_all_configured)
def test_health_response_structure(mock_check, client):
    """Verify the complete response structure."""
    response = client.get('/health')
    data = response.get_json()

    required_keys = ['status', 'adapters', 'timestamp', 'last_snapshot']
    for key in required_keys:
        assert key in data, f"Missing required key: {key}"


# ──────────────────────────────────────────────
# 5. Adapter registry matches actual adapters
# ──────────────────────────────────────────────

def test_adapter_registry_has_correct_paths():
    """Registry paths should match actual adapter file locations."""
    assert 'bikes_adapter.BikesAdapter' in ADAPTER_REGISTRY['bikes']
    assert 'routes_adapter.RoutesAdapter' in ADAPTER_REGISTRY['routes']
    assert 'traffic_adapter.TrafficAdapter' in ADAPTER_REGISTRY['traffic']
    assert 'airquality_adapter.AirQualityAdapter' in ADAPTER_REGISTRY['air_quality']
    assert 'tour_adapter.TourAdapter' in ADAPTER_REGISTRY['tour']