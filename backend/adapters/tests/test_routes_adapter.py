import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime
from backend.adapters.routes_adapter import RoutesAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def adapter():
    return RoutesAdapter()


def _make_geocode_mock(lat, lng, name="Dublin, Ireland"):
    """Return a Mock that looks like a successful Google Geocoding response."""
    m = Mock()
    m.raise_for_status = Mock()
    m.json.return_value = {
        "status": "OK",
        "results": [{"formatted_address": name, "geometry": {"location": {"lat": lat, "lng": lng}}}],
    }
    return m


@pytest.fixture
def geo_origin():
    return _make_geocode_mock(53.4853365, -6.1504482, "Donabate, Co. Dublin, Ireland")


@pytest.fixture
def geo_dest():
    return _make_geocode_mock(53.49319999999999, -6.11462, "Portrane, Co. Dublin, Ireland")


@pytest.fixture
def geo_third():
    """Extra geocode mock for a third stop in multi-stop tests."""
    return _make_geocode_mock(53.46, -6.21, "Swords, Co. Dublin, Ireland")


@pytest.fixture
def mock_api_response():
    """Google Routes API response for a single route (donabate → portrane)."""
    return {
        "routes": [{
            "duration": "278s",
            "distanceMeters": 2823,
            "polyline": {
                "encodedPolyline": (
                    "_jmeIhgpd@CmBGa@qAqBo@q@y@a@gBm@c@KoEk@_@WWg@Qs@g@cEw@gH"
                    "OgBq@wFOq@aC}G}@uBiEyHaDcF_@iAYaBOyAO{CAyBFwHNsB?eA}@qP"
                    "AeAHsAh@uAsAcEeAuHM}EWuLiAm_@AyAFgAn@gEj@qCNyAB{B"
                )
            },
            "legs": [{
                "startLocation": {"latLng": {"latitude": 53.4853365,       "longitude": -6.1504482}},
                "endLocation":   {"latLng": {"latitude": 53.49319999999999, "longitude": -6.11462}},
                "duration": "278s",
                "distanceMeters": 2823,
            }],
        }]
    }


@pytest.fixture
def mock_multistop_response():
    """Google Routes API response for a 3-stop route (swords → donabate → portrane)."""
    return {
        "routes": [{
            "duration": "1278s",
            "distanceMeters": 10400,
            "polyline": {"encodedPolyline": ""},
            "legs": [
                {
                    "startLocation": {"latLng": {"latitude": 53.46,        "longitude": -6.21}},
                    "endLocation":   {"latLng": {"latitude": 53.4853365,   "longitude": -6.1504482}},
                    "duration": "979s",
                    "distanceMeters": 7532,
                },
                {
                    "startLocation": {"latLng": {"latitude": 53.4853365,        "longitude": -6.1504482}},
                    "endLocation":   {"latLng": {"latitude": 53.49319999999999, "longitude": -6.11462}},
                    "duration": "299s",
                    "distanceMeters": 2823,
                },
            ],
        }]
    }


def _route_mock(response_data):
    """Wrap response data in a Mock that behaves like requests.Response."""
    m = Mock()
    m.raise_for_status = Mock()
    m.json.return_value = response_data
    return m


# ---------------------------------------------------------------------------
# Source name
# ---------------------------------------------------------------------------

def test_source_name(adapter):
    assert adapter.source_name() == "routes"


# ---------------------------------------------------------------------------
# Single-route tests
# ---------------------------------------------------------------------------

@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_success(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect  = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    rec = adapter.fetch(start="donabate", end="portrane")

    assert mock_post.call_count == 1
    assert rec.start == "donabate"
    assert rec.end   == "portrane"
    assert rec.duration == "278s"
    assert isinstance(rec.route, str)
    assert "_jmeIhgpd@" in rec.route


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_origin_coordinates(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    rec = adapter.fetch(start="donabate", end="portrane")

    assert hasattr(rec, 'origin_lat')
    assert hasattr(rec, 'origin_lng')
    assert rec.origin_lat == 53.4853365
    assert rec.origin_lng == -6.1504482


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_destination_coordinates(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    rec = adapter.fetch(start="donabate", end="portrane")

    assert hasattr(rec, 'dest_lat')
    assert hasattr(rec, 'dest_lng')
    assert rec.dest_lat == 53.49319999999999
    assert rec.dest_lng == -6.11462


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_distance(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    rec = adapter.fetch(start="donabate", end="portrane")

    assert hasattr(rec, 'distance_meters')
    assert rec.distance_meters == 2823


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_transport_mode(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_post.return_value = _route_mock(mock_api_response)

    for mode in ("DRIVE", "WALK", "BICYCLE"):
        mock_get.side_effect = [geo_origin, geo_dest]
        rec = adapter.fetch(start="donabate", end="portrane", transport_mode=mode)
        assert rec.transport_mode == mode


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_route_preference(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_post.return_value = _route_mock(mock_api_response)

    mock_get.side_effect = [geo_origin, geo_dest]
    rec = adapter.fetch(start="donabate", end="portrane", fast_route=True)
    assert rec.fast_route is True
    assert rec.eco_route  is False

    mock_get.side_effect = [geo_origin, geo_dest]
    rec = adapter.fetch(start="donabate", end="portrane", eco_route=True)
    assert rec.eco_route  is True
    assert rec.fast_route is False


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_with_departure_time(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    dep_time = datetime.now()
    rec = adapter.fetch(start="donabate", end="portrane", dep_time=dep_time)

    assert rec.dep_time == dep_time
    assert rec.arr_time is None


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_with_arrival_time(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    arr_time = datetime.now()
    rec = adapter.fetch(start="donabate", end="portrane", arr_time=arr_time)

    assert rec.arr_time == arr_time
    assert rec.dep_time is None


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_api_timeout(mock_post, mock_get, adapter, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.side_effect  = Exception("Timeout")

    with pytest.raises(Exception):
        adapter.fetch(start="donabate", end="portrane")


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_api_error_status(mock_post, mock_get, adapter, geo_origin, geo_dest):
    mock_get.side_effect = [geo_origin, geo_dest]
    bad = Mock()
    bad.raise_for_status.side_effect = Exception("HTTP Error")
    mock_post.return_value = bad

    with pytest.raises(Exception):
        adapter.fetch(start="donabate", end="portrane")


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_malformed_response(mock_post, mock_get, adapter, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock({"invalid": "structure"})

    with pytest.raises(KeyError):
        adapter.fetch(start="donabate", end="portrane")


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_missing_polyline(mock_post, mock_get, adapter, geo_origin, geo_dest):
    mock_get.side_effect = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock({
        "routes": [{
            "duration": "278s",
            "distanceMeters": 2823,
            # no "polyline" key
            "legs": [{
                "startLocation": {"latLng": {"latitude": 53.48, "longitude": -6.15}},
                "endLocation":   {"latLng": {"latitude": 53.49, "longitude": -6.11}},
                "duration": "278s",
                "distanceMeters": 2823,
            }],
        }]
    })

    rec = adapter.fetch(start="donabate", end="portrane")
    assert rec.route is None or rec.route == ""


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_duration_parsing(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    rec = adapter.fetch(start="donabate", end="portrane")
    assert rec.duration in ["278s", 278]


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_invalid_transport_mode(mock_post, mock_get, adapter, geo_origin, geo_dest):
    mock_get.side_effect  = [geo_origin, geo_dest]
    mock_post.side_effect = Exception("Invalid transport mode")

    with pytest.raises(Exception):
        adapter.fetch(start="donabate", end="portrane", transport_mode="INVALID")


def test_fetch_both_times_specified(adapter):
    with pytest.raises(ValueError):
        adapter.fetch(
            start="donabate", end="portrane",
            dep_time=datetime.now(),
            arr_time=datetime.now(),
        )


def test_fetch_both_route_preferences(adapter):
    with pytest.raises(ValueError):
        adapter.fetch(
            start="donabate", end="portrane",
            fast_route=True, eco_route=True,
        )


# ---------------------------------------------------------------------------
# Multi-stop tests
# ---------------------------------------------------------------------------

@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_fetch_multistop_route(mock_post, mock_get, adapter, mock_multistop_response, geo_third, geo_origin, geo_dest):
    # swords → donabate (waypoint) → portrane
    mock_get.side_effect   = [geo_third, geo_dest, geo_origin]   # start, end, waypoint
    mock_post.return_value = _route_mock(mock_multistop_response)

    rec = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    assert rec.is_multi_stop() is True
    assert rec.waypoints == ["donabate"]


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_multistop_route_order(mock_post, mock_get, adapter, mock_multistop_response, geo_third, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_third, geo_dest, geo_origin]
    mock_post.return_value = _route_mock(mock_multistop_response)

    rec = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    assert rec.multi_stop_data.optimal_route_order == ["swords", "donabate", "portrane"]
    assert rec.multi_stop_data.number_of_stops == 3


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_multistop_total_metrics(mock_post, mock_get, adapter, mock_multistop_response, geo_third, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_third, geo_dest, geo_origin]
    mock_post.return_value = _route_mock(mock_multistop_response)

    rec = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])

    assert rec.multi_stop_data.total_duration_seconds == 1278
    assert rec.multi_stop_data.total_duration_formatted == "21m"
    assert rec.multi_stop_data.total_distance_km == 10.4


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_multistop_legs(mock_post, mock_get, adapter, mock_multistop_response, geo_third, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_third, geo_dest, geo_origin]
    mock_post.return_value = _route_mock(mock_multistop_response)

    rec  = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])
    legs = rec.multi_stop_data.legs

    assert len(legs) == 2
    assert legs[0].from_location == "swords"
    assert legs[0].to_location   == "donabate"
    assert legs[0].duration_seconds == 979
    assert legs[0].distance_km == 7.5

    assert legs[1].from_location == "donabate"
    assert legs[1].to_location   == "portrane"
    assert legs[1].duration_seconds == 299
    assert legs[1].distance_km == 2.8


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_multistop_with_multiple_waypoints(mock_post, mock_get, adapter, geo_origin, geo_dest, geo_third):
    mock_get.side_effect = [geo_origin, geo_dest, geo_origin, geo_dest]   # A, D, B, C geocodes
    mock_post.return_value = _route_mock({
        "routes": [{
            "duration": "2000s",
            "distanceMeters": 15500,
            "polyline": {"encodedPolyline": ""},
            "legs": [
                {"startLocation": {"latLng": {"latitude": 53.4, "longitude": -6.2}},
                 "endLocation":   {"latLng": {"latitude": 53.42, "longitude": -6.18}},
                 "duration": "600s", "distanceMeters": 5000},
                {"startLocation": {"latLng": {"latitude": 53.42, "longitude": -6.18}},
                 "endLocation":   {"latLng": {"latitude": 53.45, "longitude": -6.15}},
                 "duration": "700s", "distanceMeters": 5500},
                {"startLocation": {"latLng": {"latitude": 53.45, "longitude": -6.15}},
                 "endLocation":   {"latLng": {"latitude": 53.49, "longitude": -6.11}},
                 "duration": "700s", "distanceMeters": 5000},
            ],
        }]
    })

    rec = adapter.fetch(start="A", end="D", waypoints=["B", "C"])

    assert len(rec.waypoints) == 2
    assert rec.multi_stop_data.number_of_stops == 4
    assert len(rec.multi_stop_data.legs) == 3


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_multistop_duration_sum(mock_post, mock_get, adapter, mock_multistop_response, geo_third, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_third, geo_dest, geo_origin]
    mock_post.return_value = _route_mock(mock_multistop_response)

    rec  = adapter.fetch(start="swords", end="portrane", waypoints=["donabate"])
    legs = rec.multi_stop_data.legs

    total_leg_duration = sum(leg.duration_seconds for leg in legs)
    assert total_leg_duration == 979 + 299
    assert total_leg_duration == 1278
    assert total_leg_duration == rec.multi_stop_data.total_duration_seconds


@patch('backend.adapters.routes_adapter.requests.get')
@patch('backend.adapters.routes_adapter.requests.post')
def test_single_stop_is_not_multistop(mock_post, mock_get, adapter, mock_api_response, geo_origin, geo_dest):
    mock_get.side_effect   = [geo_origin, geo_dest]
    mock_post.return_value = _route_mock(mock_api_response)

    rec = adapter.fetch(start="donabate", end="portrane")

    assert rec.is_multi_stop() is False
    assert len(rec.waypoints) == 0
    assert rec.multi_stop_data is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
