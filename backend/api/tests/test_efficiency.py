"""
Tests for the Fleet Efficiency endpoint and its helpers.

Covers:
  - Pure Python helpers: _haversine_km, _dist_matrix, _vrp_nearest_neighbour,
    _two_opt, _score, _geocode_stop
  - POST /routing/efficiency  action="build"
  - POST /routing/efficiency  action="analyse"
  - Geocoding fallback: Google → Nominatim → 400
  - Nominatim function unit tests

Run: pytest backend/api/tests/test_efficiency.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from backend.api.endpoints.efficiency import (
    efficiency_bp,
    _haversine_km,
    _dist_matrix,
    _vrp_nearest_neighbour,
    _two_opt,
    _score,
    _geocode_stop,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    application = Flask(__name__)
    application.register_blueprint(efficiency_bp)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


# Minimal fake geometry returned by the mocked route helpers
_FAKE_ROUTE = {
    "geometry": {
        "type": "LineString",
        "coordinates": [[-6.27, 53.34], [-6.26, 53.35]],
    },
    "distance_meters": 1500,
    "distance_km": 1.5,
    "duration_seconds": 360,
    "duration_minutes": 6,
}

# Four Dublin-area pin coords used across multiple tests
_PINS = [
    {"lat": 53.3300, "lon": -6.2600},
    {"lat": 53.3400, "lon": -6.2700},
    {"lat": 53.3500, "lon": -6.2800},
    {"lat": 53.3600, "lon": -6.2900},
]


# ---------------------------------------------------------------------------
# Helpers — _haversine_km
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self):
        assert _haversine_km(53.34, -6.26, 53.34, -6.26) == 0.0

    def test_known_distance_approx(self):
        # Trinity College → St Stephen's Green ≈ 0.7 km
        d = _haversine_km(53.3438, -6.2546, 53.3382, -6.2591)
        assert 0.4 < d < 1.2

    def test_symmetric(self):
        a = (53.34, -6.26)
        b = (53.36, -6.28)
        assert abs(_haversine_km(*a, *b) - _haversine_km(*b, *a)) < 1e-9

    def test_returns_float(self):
        assert isinstance(_haversine_km(53.34, -6.26, 53.35, -6.27), float)


# ---------------------------------------------------------------------------
# Helpers — _dist_matrix
# ---------------------------------------------------------------------------

class TestDistMatrix:
    def test_shape(self):
        coords = [(53.33, -6.26), (53.34, -6.27), (53.35, -6.28)]
        d = _dist_matrix(coords)
        assert len(d) == 3
        assert all(len(row) == 3 for row in d)

    def test_diagonal_zero(self):
        coords = [(53.33, -6.26), (53.34, -6.27)]
        d = _dist_matrix(coords)
        assert d[0][0] == 0.0
        assert d[1][1] == 0.0

    def test_symmetric(self):
        coords = [(53.33, -6.26), (53.34, -6.27), (53.35, -6.28)]
        d = _dist_matrix(coords)
        assert abs(d[0][1] - d[1][0]) < 1e-9
        assert abs(d[0][2] - d[2][0]) < 1e-9

    def test_single_point(self):
        d = _dist_matrix([(53.34, -6.26)])
        assert d == [[0.0]]


# ---------------------------------------------------------------------------
# Helpers — _vrp_nearest_neighbour
# ---------------------------------------------------------------------------

class TestVRP:
    def _make_dist(self, n):
        coords = [(53.30 + i * 0.01, -6.26) for i in range(n)]
        return _dist_matrix(coords)

    def test_single_vehicle_gets_all_stops(self):
        d = self._make_dist(4)
        routes = _vrp_nearest_neighbour(d, 4, 1)
        assert len(routes) == 1
        assert sorted(routes[0]) == [0, 1, 2, 3]

    def test_two_vehicles_partition_all_stops(self):
        d = self._make_dist(4)
        routes = _vrp_nearest_neighbour(d, 4, 2)
        assert len(routes) == 2
        all_stops = sorted(s for r in routes for s in r)
        assert all_stops == [0, 1, 2, 3]

    def test_no_stop_duplicated(self):
        d = self._make_dist(6)
        routes = _vrp_nearest_neighbour(d, 6, 3)
        all_stops = [s for r in routes for s in r]
        assert len(all_stops) == len(set(all_stops))

    def test_returns_correct_number_of_routes(self):
        d = self._make_dist(5)
        routes = _vrp_nearest_neighbour(d, 5, 3)
        assert len(routes) == 3


# ---------------------------------------------------------------------------
# Helpers — _two_opt
# ---------------------------------------------------------------------------

class TestTwoOpt:
    def test_result_has_same_stops(self):
        coords = [(53.33, -6.26), (53.34, -6.27), (53.35, -6.28), (53.36, -6.29)]
        d = _dist_matrix(coords)
        original = [0, 3, 1, 2]
        result = _two_opt(list(original), d)
        assert sorted(result) == [0, 1, 2, 3]

    def test_short_route_unchanged_length(self):
        coords = [(53.33, -6.26), (53.34, -6.27), (53.35, -6.28)]
        d = _dist_matrix(coords)
        result = _two_opt([0, 1, 2], d)
        assert len(result) == 3

    def test_returns_list(self):
        coords = [(53.33, -6.26), (53.34, -6.27), (53.35, -6.28), (53.36, -6.29)]
        d = _dist_matrix(coords)
        assert isinstance(_two_opt([0, 1, 2, 3], d), list)

    def test_does_not_increase_distance(self):
        coords = [(53.33, -6.26), (53.36, -6.29), (53.34, -6.27), (53.35, -6.28)]
        d = _dist_matrix(coords)
        original_dist = sum(d[r][r_next] for r, r_next in zip([0, 1, 2, 3], [1, 2, 3, 0][:-1]))
        improved = _two_opt([0, 1, 2, 3], d)
        improved_dist = sum(d[improved[i]][improved[i+1]] for i in range(len(improved)-1))
        assert improved_dist <= original_dist + 1e-9


# ---------------------------------------------------------------------------
# Helpers — _score
# ---------------------------------------------------------------------------

class TestScore:
    def test_score_in_range(self):
        coords = [(53.33, -6.26), (53.34, -6.27), (53.35, -6.28), (53.36, -6.29)]
        d = _dist_matrix(coords)
        score, _ = _score([[0, 1], [2, 3]], d)
        assert 0 <= score <= 100

    def test_returns_vehicle_distances(self):
        coords = [(53.33, -6.26), (53.34, -6.27), (53.35, -6.28)]
        d = _dist_matrix(coords)
        _, distances = _score([[0, 1, 2]], d)
        assert len(distances) == 1
        assert distances[0] > 0

    def test_empty_vehicle_penalises_score(self):
        coords = [(53.33, -6.26), (53.34, -6.27)]
        d = _dist_matrix(coords)
        score_with_empty, _ = _score([[0, 1], []], d)
        score_balanced, _   = _score([[0], [1]], d)
        assert score_with_empty < score_balanced

    def test_single_vehicle_single_stop(self):
        coords = [(53.34, -6.26)]
        d = _dist_matrix(coords)
        score, distances = _score([[0]], d)
        assert 0 <= score <= 100
        assert distances == [0.0]


# ---------------------------------------------------------------------------
# Helpers — _geocode_stop (pin bypass)
# ---------------------------------------------------------------------------

class TestGeocodeStop:
    def test_pin_drop_bypasses_geocoding(self):
        stop = _geocode_stop({"lat": 53.34, "lon": -6.27})
        assert stop["lat"] == 53.34
        assert stop["lon"] == -6.27

    def test_pin_drop_preserves_name(self):
        stop = _geocode_stop({"lat": 53.34, "lon": -6.27, "name": "My Depot"})
        assert stop["name"] == "My Depot"

    def test_pin_drop_generates_name_when_absent(self):
        stop = _geocode_stop({"lat": 53.34, "lon": -6.27})
        assert "53.34" in stop["name"]

    @patch("backend.api.endpoints.efficiency._adapter")
    def test_text_address_uses_google(self, mock_adapter):
        mock_adapter.geocode.return_value = (53.34, -6.26, "Trinity College, Dublin")
        stop = _geocode_stop("Trinity College")
        assert stop["lat"] == 53.34
        mock_adapter.geocode.assert_called_once()

    @patch("backend.api.endpoints.efficiency._geocode_nominatim")
    @patch("backend.api.endpoints.efficiency._adapter")
    def test_text_address_falls_back_to_nominatim(self, mock_adapter, mock_nominatim):
        mock_adapter.geocode.side_effect = RuntimeError("no key")
        mock_nominatim.return_value = (53.35, -6.27, "Some Place, Dublin")
        stop = _geocode_stop("Some Place")
        assert stop["lat"] == 53.35
        mock_nominatim.assert_called_once()


# ---------------------------------------------------------------------------
# Endpoint — Build action
# ---------------------------------------------------------------------------

class TestBuildEndpoint:

    def _pin_payload(self, n_stops=4, n_vehicles=2, **extra):
        stops = [{"lat": 53.30 + i * 0.01, "lon": -6.26} for i in range(n_stops)]
        return {"action": "build", "stops": stops, "vehicles": n_vehicles,
                "transport": "driving", **extra}

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_pin_stops_returns_200(self, mock_local, mock_routes, client):
        resp = client.post("/routing/efficiency", json=self._pin_payload())
        assert resp.status_code == 200

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_response_has_required_keys(self, mock_local, mock_routes, client):
        resp = client.post("/routing/efficiency", json=self._pin_payload())
        data = resp.get_json()
        for key in ("routes", "score", "suggestions", "total_distance_km",
                    "n_vehicles", "n_stops"):
            assert key in data, f"Missing key: {key}"

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_all_stops_assigned_across_vehicles(self, mock_local, mock_routes, client):
        resp = client.post("/routing/efficiency", json=self._pin_payload(n_stops=6, n_vehicles=3))
        data = resp.get_json()
        assert resp.status_code == 200
        total = sum(len(r["stops"]) for r in data["routes"])
        assert total == 6

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_score_in_range(self, mock_local, mock_routes, client):
        resp = client.post("/routing/efficiency", json=self._pin_payload())
        assert 0 <= resp.get_json()["score"] <= 100

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_n_vehicles_matches_request(self, mock_local, mock_routes, client):
        resp = client.post("/routing/efficiency", json=self._pin_payload(n_stops=4, n_vehicles=2))
        assert resp.get_json()["n_vehicles"] == 2

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_n_stops_matches_input(self, mock_local, mock_routes, client):
        resp = client.post("/routing/efficiency", json=self._pin_payload(n_stops=5))
        assert resp.get_json()["n_stops"] == 5

    def test_empty_stops_returns_400(self, client):
        resp = client.post("/routing/efficiency",
                           json={"action": "build", "stops": [], "vehicles": 2})
        assert resp.status_code == 400

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=_FAKE_ROUTE)
    def test_geometry_included_when_route_found(self, mock_routes, client):
        payload = self._pin_payload(n_stops=2, n_vehicles=1)
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["routes"][0]["geometry"] is not None

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_geometry_null_when_no_route(self, mock_local, mock_routes, client):
        payload = self._pin_payload(n_stops=2, n_vehicles=1)
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["routes"][0]["geometry"] is None

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    @patch("backend.api.endpoints.efficiency._adapter")
    def test_depot_prepended_and_appended(self, mock_adapter, mock_local, mock_routes, client):
        mock_adapter.geocode.return_value = (53.30, -6.25, "Depot")
        payload = self._pin_payload(n_stops=2, n_vehicles=1,
                                    start="Depot", end="Depot")
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        route_stops = resp.get_json()["routes"][0]["stops"]
        # depot + 2 stops + depot = 4
        assert len(route_stops) == 4

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    @patch("backend.api.endpoints.efficiency._adapter")
    def test_pin_depot_bypasses_geocoding(self, mock_adapter, mock_local, mock_routes, client):
        payload = self._pin_payload(n_stops=2, n_vehicles=1,
                                    start={"lat": 53.30, "lon": -6.25, "name": "Depot"})
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        mock_adapter.geocode.assert_not_called()

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_more_vehicles_than_stops_capped(self, mock_local, mock_routes, client):
        # 2 stops, 5 vehicles requested → capped at 2
        payload = self._pin_payload(n_stops=2, n_vehicles=5)
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        assert resp.get_json()["n_vehicles"] <= 2

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_local_route_fallback_used_for_driving(self, mock_local, mock_routes, client):
        mock_local.return_value = _FAKE_ROUTE
        payload = self._pin_payload(n_stops=2, n_vehicles=1)
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        assert mock_local.called

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_no_local_fallback_for_cycling(self, mock_local, mock_routes, client):
        payload = {"action": "build",
                   "stops": [{"lat": 53.33, "lon": -6.26}, {"lat": 53.34, "lon": -6.27}],
                   "vehicles": 1, "transport": "cycling"}
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        mock_local.assert_not_called()


# ---------------------------------------------------------------------------
# Endpoint — Analyse action
# ---------------------------------------------------------------------------

class TestAnalyseEndpoint:

    def _route_payload(self, routes, **extra):
        return {"action": "analyse", "existing_routes": routes,
                "transport": "driving", **extra}

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_analyse_pin_stops_returns_200(self, mock_local, mock_routes, client):
        payload = self._route_payload([
            [{"lat": 53.33, "lon": -6.26}, {"lat": 53.34, "lon": -6.27}],
            [{"lat": 53.35, "lon": -6.28}, {"lat": 53.36, "lon": -6.29}],
        ])
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_analyse_n_vehicles_and_stops_correct(self, mock_local, mock_routes, client):
        payload = self._route_payload([
            [{"lat": 53.33, "lon": -6.26}, {"lat": 53.34, "lon": -6.27}],
            [{"lat": 53.35, "lon": -6.28}],
        ])
        resp = client.post("/routing/efficiency", json=payload)
        data = resp.get_json()
        assert data["n_vehicles"] == 2
        assert data["n_stops"] == 3

    def test_analyse_empty_routes_returns_400(self, client):
        resp = client.post("/routing/efficiency",
                           json={"action": "analyse", "existing_routes": []})
        assert resp.status_code == 400

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_analyse_returns_suggestions_list(self, mock_local, mock_routes, client):
        payload = self._route_payload([
            [{"lat": 53.33, "lon": -6.26}, {"lat": 53.36, "lon": -6.29}],
            [],
        ])
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["suggestions"], list)

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    def test_analyse_score_in_range(self, mock_local, mock_routes, client):
        payload = self._route_payload([
            [{"lat": 53.33, "lon": -6.26}, {"lat": 53.34, "lon": -6.27}],
            [{"lat": 53.35, "lon": -6.28}, {"lat": 53.36, "lon": -6.29}],
        ])
        resp = client.post("/routing/efficiency", json=payload)
        assert 0 <= resp.get_json()["score"] <= 100

    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    @patch("backend.api.endpoints.efficiency._adapter")
    def test_analyse_depot_prepended_appended(self, mock_adapter, mock_local, mock_routes, client):
        mock_adapter.geocode.return_value = (53.30, -6.25, "Depot")
        payload = self._route_payload(
            [[{"lat": 53.33, "lon": -6.26}, {"lat": 53.34, "lon": -6.27}]],
            start="Depot", end="Depot",
        )
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        route_stops = resp.get_json()["routes"][0]["stops"]
        assert len(route_stops) == 4  # depot + 2 stops + depot


# ---------------------------------------------------------------------------
# Geocoding fallback: Google → Nominatim → 400
# ---------------------------------------------------------------------------

class TestGeocodingFallback:

    @patch("backend.api.endpoints.efficiency._geocode_nominatim")
    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    @patch("backend.api.endpoints.efficiency._adapter")
    def test_nominatim_called_when_google_fails(self, mock_adapter, mock_local,
                                                mock_routes, mock_nominatim, client):
        mock_adapter.geocode.side_effect = RuntimeError("no API key")
        mock_nominatim.return_value = (53.34, -6.27, "Trinity College, Dublin")
        payload = {
            "action": "build",
            "stops": ["Trinity College", "St Stephen's Green"],
            "vehicles": 1,
            "transport": "driving",
        }
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        assert mock_nominatim.call_count == 2

    @patch("backend.api.endpoints.efficiency._geocode_nominatim")
    @patch("backend.api.endpoints.efficiency._adapter")
    def test_400_when_both_geocoders_fail(self, mock_adapter, mock_nominatim, client):
        mock_adapter.geocode.side_effect = RuntimeError("no key")
        mock_nominatim.side_effect = RuntimeError("no results")
        payload = {
            "action": "build",
            "stops": ["Nonexistent Place XYZ123"],
            "vehicles": 1,
        }
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    @patch("backend.api.endpoints.efficiency._geocode_nominatim")
    @patch("backend.api.endpoints.efficiency._call_routes", return_value=None)
    @patch("backend.api.endpoints.efficiency._call_local_route", return_value=None)
    @patch("backend.api.endpoints.efficiency._adapter")
    def test_google_success_does_not_call_nominatim(self, mock_adapter, mock_local,
                                                     mock_routes, mock_nominatim, client):
        mock_adapter.geocode.return_value = (53.34, -6.26, "Trinity College, Dublin")
        payload = {
            "action": "build",
            "stops": ["Trinity College"],
            "vehicles": 1,
            "transport": "driving",
        }
        resp = client.post("/routing/efficiency", json=payload)
        assert resp.status_code == 200
        mock_nominatim.assert_not_called()


# ---------------------------------------------------------------------------
# Nominatim function unit tests (patches requests.get in routing module)
# ---------------------------------------------------------------------------

class TestNominatim:

    @patch("backend.api.endpoints.routing.requests.get")
    def test_returns_lat_lon_name(self, mock_get):
        from backend.api.endpoints.routing import _geocode_nominatim
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = [
            {"lat": "53.3438", "lon": "-6.2546",
             "display_name": "Trinity College, Dublin, Ireland"},
        ]
        lat, lon, name = _geocode_nominatim("Trinity College Dublin")
        assert abs(lat - 53.3438) < 1e-4
        assert abs(lon - (-6.2546)) < 1e-4
        assert "Trinity" in name

    @patch("backend.api.endpoints.routing.requests.get")
    def test_appends_dublin_when_city_missing(self, mock_get):
        from backend.api.endpoints.routing import _geocode_nominatim
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = [
            {"lat": "53.33", "lon": "-6.26", "display_name": "Grafton Street, Dublin"}
        ]
        _geocode_nominatim("Grafton Street")
        params = mock_get.call_args[1]["params"]
        assert "Dublin" in params["q"]

    @patch("backend.api.endpoints.routing.requests.get")
    def test_does_not_double_append_dublin(self, mock_get):
        from backend.api.endpoints.routing import _geocode_nominatim
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = [
            {"lat": "53.33", "lon": "-6.26", "display_name": "Dublin Airport"}
        ]
        _geocode_nominatim("Dublin Airport")
        params = mock_get.call_args[1]["params"]
        assert params["q"].lower().count("dublin") == 1

    @patch("backend.api.endpoints.routing.requests.get")
    def test_raises_on_empty_results(self, mock_get):
        from backend.api.endpoints.routing import _geocode_nominatim
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = []
        with pytest.raises(RuntimeError):
            _geocode_nominatim("Nowhere XYZ999")

    @patch("backend.api.endpoints.routing.requests.get")
    def test_sets_user_agent_header(self, mock_get):
        from backend.api.endpoints.routing import _geocode_nominatim
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = [
            {"lat": "53.34", "lon": "-6.26", "display_name": "Place, Dublin"}
        ]
        _geocode_nominatim("Some Place Dublin")
        headers = mock_get.call_args[1]["headers"]
        assert "User-Agent" in headers
