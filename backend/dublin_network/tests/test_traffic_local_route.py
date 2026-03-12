"""
Tests for GET /traffic/local-route endpoint (traffic.py)
=========================================================
Mocks TrafficPredictor and DublinRouter so these tests run without any
CSV files, XML files, or external APIs.

Run: pytest backend/dublin_network/tests/test_traffic_local_route.py -v
"""

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

from backend.api.endpoints.traffic import traffic_bp
from backend.dublin_network.router import RouteResult, RouteStep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_step(road="O'Connell Street", length=200.0, ff_time=15.0,
               act_time=20.0, load=0.2):
    return RouteStep(
        edge_id="edge_123",
        road_name=road,
        edge_type="highway.primary",
        length_m=length,
        free_flow_time_s=ff_time,
        actual_time_s=act_time,
        load_ratio=load,
        from_lat=53.3498,
        from_lon=-6.2603,
        to_lat=53.3510,
        to_lon=-6.2590,
    )


def _make_route_result(found=True, distance=500.0, ff_time=40.0,
                       actual_time=50.0, steps=None):
    steps = steps or [_make_step()]
    return RouteResult(
        found=found,
        from_junction="jA",
        to_junction="jB",
        total_distance_m=distance,
        total_free_flow_time_s=ff_time,
        total_actual_time_s=actual_time,
        traffic_delay_s=actual_time - ff_time,
        steps=steps,
        geometry=[(53.3498, -6.2603), (53.3510, -6.2590)],
        from_snap_m=5.0,
        to_snap_m=3.0,
    )


@pytest.fixture
def mock_model():
    m = MagicMock()
    m.congestion_at.return_value = "medium"
    m._edge_peak = 100
    m._edge_counts = [{} for _ in range(96)]
    return m


@pytest.fixture
def mock_router():
    m = MagicMock()
    m.route.return_value = _make_route_result()
    return m


@pytest.fixture
def app(mock_model, mock_router):
    """
    Flask test app with traffic blueprint and all module-level singletons
    (TrafficPredictor, DublinRouter) replaced with mocks.
    The fixture yields only the Flask app so pytest-flask works correctly.
    """
    with (
        patch("backend.api.endpoints.traffic._traffic_model", mock_model),
        patch("backend.api.endpoints.traffic._router", mock_router),
    ):
        flask_app = Flask(__name__)
        flask_app.register_blueprint(traffic_bp)
        flask_app.config["TESTING"] = True
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mocks(mock_model, mock_router):
    return mock_model, mock_router


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    _VALID = "?from_lat=53.3498&from_lon=-6.2603&to_lat=53.3418&to_lon=-6.2675"

    def test_returns_200(self, client):
        resp = client.get(f"/traffic/local-route{self._VALID}")
        assert resp.status_code == 200

    def test_returns_json(self, client):
        resp = client.get(f"/traffic/local-route{self._VALID}")
        assert resp.content_type == "application/json"

    def test_found_true(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert data["found"] is True

    def test_contains_required_fields(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        for key in ("found", "congestion_level", "traffic_applied",
                    "total_distance_m", "total_distance_km",
                    "total_actual_time_s", "total_actual_time_min",
                    "traffic_delay_s", "geometry", "steps"):
            assert key in data, f"Missing key: {key}"

    def test_geometry_is_list(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert isinstance(data["geometry"], list)

    def test_steps_is_list(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert isinstance(data["steps"], list)

    def test_step_has_road_name(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        step = data["steps"][0]
        assert "road" in step
        assert step["road"] == "O'Connell Street"

    def test_step_has_distance_and_time(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        step = data["steps"][0]
        assert step["length_m"] == 200.0
        assert step["actual_time_s"] == 20.0

    def test_step_has_from_to_coords(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        step = data["steps"][0]
        assert "from" in step
        assert "to" in step
        assert "lat" in step["from"]
        assert "lon" in step["from"]

    def test_congestion_level_from_model(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert data["congestion_level"] == "medium"

    def test_traffic_applied_default_true(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert data["traffic_applied"] is True

    def test_snap_distances_present(self, client):
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert data["from_snap_m"] == 5.0
        assert data["to_snap_m"] == 3.0


# ---------------------------------------------------------------------------
# 2. Traffic toggling
# ---------------------------------------------------------------------------

class TestTrafficToggle:
    _BASE = "/traffic/local-route?from_lat=53.3498&from_lon=-6.2603&to_lat=53.34&to_lon=-6.26"

    def test_apply_traffic_false_passes_empty_loads(self, client, mocks):
        _, mock_router = mocks
        client.get(f"{self._BASE}&apply_traffic=false")
        call_kwargs = mock_router.route.call_args.kwargs
        assert call_kwargs["edge_loads"] == {}

    def test_apply_traffic_true_passes_loads(self, client, mocks):
        mock_model, mock_router = mocks
        # Inject some loads into the model's bin counts
        mock_model._edge_counts[
            # current time bin — any non-empty dict will do
            0
        ] = {"edge_X": 42}
        client.get(f"{self._BASE}&apply_traffic=true")
        call_kwargs = mock_router.route.call_args.kwargs
        # edge_loads should have been populated from _edge_counts
        assert isinstance(call_kwargs["edge_loads"], dict)

    def test_apply_traffic_false_response_field(self, client):
        data = client.get(f"{self._BASE}&apply_traffic=false").get_json()
        assert data["traffic_applied"] is False


# ---------------------------------------------------------------------------
# 3. Missing / bad parameters
# ---------------------------------------------------------------------------

class TestBadParameters:
    def test_missing_all_params_returns_400(self, client):
        resp = client.get("/traffic/local-route")
        assert resp.status_code == 400

    def test_missing_to_lat_returns_400(self, client):
        resp = client.get("/traffic/local-route?from_lat=53.34&from_lon=-6.26&to_lon=-6.25")
        assert resp.status_code == 400

    def test_non_numeric_param_returns_400(self, client):
        resp = client.get("/traffic/local-route?from_lat=abc&from_lon=-6.26&to_lat=53.34&to_lon=-6.25")
        assert resp.status_code == 400

    def test_400_response_contains_error_key(self, client):
        data = client.get("/traffic/local-route").get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# 4. Route not found (404)
# ---------------------------------------------------------------------------

class TestRouteNotFound:
    _VALID = "?from_lat=53.3498&from_lon=-6.2603&to_lat=53.3418&to_lon=-6.2675"

    def test_returns_404_when_router_returns_not_found(self, client, mocks):
        _, mock_router = mocks
        mock_router.route.return_value = RouteResult(
            found=False,
            from_junction="jA", to_junction="jB",
            total_distance_m=0, total_free_flow_time_s=0,
            total_actual_time_s=0, traffic_delay_s=0,
            steps=[], geometry=[],
            from_snap_m=10.0, to_snap_m=5.0,
        )
        resp = client.get(f"/traffic/local-route{self._VALID}")
        assert resp.status_code == 404

    def test_404_response_has_found_false(self, client, mocks):
        _, mock_router = mocks
        mock_router.route.return_value = RouteResult(
            found=False,
            from_junction="jA", to_junction="jB",
            total_distance_m=0, total_free_flow_time_s=0,
            total_actual_time_s=0, traffic_delay_s=0,
            steps=[], geometry=[],
            from_snap_m=10.0, to_snap_m=5.0,
        )
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert data["found"] is False
        assert "error" in data

    def test_404_includes_snap_distances(self, client, mocks):
        _, mock_router = mocks
        mock_router.route.return_value = RouteResult(
            found=False,
            from_junction="jX", to_junction="jY",
            total_distance_m=0, total_free_flow_time_s=0,
            total_actual_time_s=0, traffic_delay_s=0,
            steps=[], geometry=[],
            from_snap_m=999.0, to_snap_m=888.0,
        )
        data = client.get(f"/traffic/local-route{self._VALID}").get_json()
        assert data["from_snap_m"] == 999.0
        assert data["to_snap_m"] == 888.0


# ---------------------------------------------------------------------------
# 5. Router is called with the correct coordinates
# ---------------------------------------------------------------------------

class TestRouterCalledCorrectly:
    def test_router_receives_correct_lat_lon(self, client, mocks):
        _, mock_router = mocks
        mock_router.route.return_value = _make_route_result()
        client.get(
            "/traffic/local-route"
            "?from_lat=53.3498&from_lon=-6.2603"
            "&to_lat=53.3418&to_lon=-6.2675"
        )
        call_kwargs = mock_router.route.call_args.kwargs
        assert abs(call_kwargs["from_lat"] - 53.3498) < 1e-6
        assert abs(call_kwargs["from_lon"] - (-6.2603)) < 1e-6
        assert abs(call_kwargs["to_lat"] - 53.3418) < 1e-6
        assert abs(call_kwargs["to_lon"] - (-6.2675)) < 1e-6

    def test_post_not_allowed(self, client):
        resp = client.post(
            "/traffic/local-route"
            "?from_lat=53.34&from_lon=-6.26&to_lat=53.35&to_lon=-6.25"
        )
        assert resp.status_code == 405
