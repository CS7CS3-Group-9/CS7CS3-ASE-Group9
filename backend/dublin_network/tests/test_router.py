"""
Tests for DublinRouter (router.py)
====================================
Builds a tiny DublinNetwork manually (no XML parsing) so tests are fast
and deterministic.  The graph has 4 junctions and 5 edges:

    jA --[AB, 100m, 10m/s]--> jB --[BC, 100m, 10m/s]--> jC
    jA --[AC, 350m, 10m/s]-------------------------> jC   (longer direct)
    jB --[BD, 100m, 10m/s]--> jD
    jC --[CD, 100m, 10m/s]--> jD

Shortest jA→jC:  via AB+BC = 200m (20s)  vs  AC = 350m (35s)
Shortest jA→jD:  AB+BC+CD = 300m (30s)

Run: pytest backend/dublin_network/tests/test_router.py -v
"""

import math
import pytest

from backend.dublin_network.network_parser import DublinNetwork, EdgeInfo
from backend.dublin_network.router import DublinRouter, _CONGESTION_FACTOR

# ---------------------------------------------------------------------------
# Helpers to build a synthetic network without parsing any XML
# ---------------------------------------------------------------------------

def _make_edge(eid, from_node, to_node, name, length, speed=10.0,
               etype="highway.primary",
               from_lat=53.33, from_lon=-6.26,
               to_lat=53.34, to_lon=-6.25) -> EdgeInfo:
    return EdgeInfo(
        id=eid,
        from_node=from_node,
        to_node=to_node,
        name=name,
        edge_type=etype,
        speed=speed,
        length=length,
        mid_lat=round((from_lat + to_lat) / 2, 6),
        mid_lon=round((from_lon + to_lon) / 2, 6),
        from_lat=from_lat,
        from_lon=from_lon,
        to_lat=to_lat,
        to_lon=to_lon,
        driveable=True,
    )


@pytest.fixture
def small_net():
    """4-junction, 5-edge synthetic network (no XML file required)."""
    net = object.__new__(DublinNetwork)
    net.junctions = {
        "jA": (53.330, -6.270),
        "jB": (53.335, -6.260),
        "jC": (53.340, -6.250),
        "jD": (53.345, -6.240),
    }
    edges = {
        "AB": _make_edge("AB", "jA", "jB", "Alpha Street", 100,
                         from_lat=53.330, from_lon=-6.270,
                         to_lat=53.335, to_lon=-6.260),
        "BC": _make_edge("BC", "jB", "jC", "Beta Road", 100,
                         from_lat=53.335, from_lon=-6.260,
                         to_lat=53.340, to_lon=-6.250),
        "AC": _make_edge("AC", "jA", "jC", "Direct Lane", 350,
                         from_lat=53.330, from_lon=-6.270,
                         to_lat=53.340, to_lon=-6.250),
        "BD": _make_edge("BD", "jB", "jD", "Bravo Drive", 100,
                         from_lat=53.335, from_lon=-6.260,
                         to_lat=53.345, to_lon=-6.240),
        "CD": _make_edge("CD", "jC", "jD", "Charlie Close", 100,
                         from_lat=53.340, from_lon=-6.250,
                         to_lat=53.345, to_lon=-6.240),
    }
    net.edges = edges
    net.graph = {
        "jA": [("jB", "AB"), ("jC", "AC")],
        "jB": [("jC", "BC"), ("jD", "BD")],
        "jC": [("jD", "CD")],
    }
    net.road_nodes = {"jA", "jB", "jC", "jD"}
    return net


@pytest.fixture
def router(small_net):
    return DublinRouter(network=small_net)


# ---------------------------------------------------------------------------
# 1. Basic routing
# ---------------------------------------------------------------------------

class TestBasicRouting:
    def test_route_found_between_connected_nodes(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        assert result.found is True

    def test_route_not_found_when_unreachable(self, router):
        # jD has no outgoing edges so it can't be an origin
        # Route from jD to jA — unreachable (no path back)
        result = router.route(53.345, -6.240, 53.330, -6.270)
        assert result.found is False

    def test_same_origin_destination_returns_empty_steps(self, router):
        result = router.route(53.330, -6.270, 53.330, -6.270)
        assert result.found is True
        assert result.steps == []
        assert result.total_distance_m == 0.0

    def test_shortest_path_avoids_longer_direct_route(self, router):
        # jA→jC: AB+BC = 200m wins over AC = 350m
        result = router.route(53.330, -6.270, 53.340, -6.250)
        edge_ids = [s.edge_id for s in result.steps]
        assert "AB" in edge_ids
        assert "BC" in edge_ids
        assert "AC" not in edge_ids

    def test_total_distance_correct(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        assert abs(result.total_distance_m - 200.0) < 0.5

    def test_multi_hop_route(self, router):
        # jA→jD: AB+BC+CD = 300m (faster than AB+BD = 200m? No: AB+BD=200m)
        # Actually AB+BD = 100+100 = 200m wins
        result = router.route(53.330, -6.270, 53.345, -6.240)
        assert result.found is True
        edge_ids = [s.edge_id for s in result.steps]
        assert "AB" in edge_ids


# ---------------------------------------------------------------------------
# 2. Step content
# ---------------------------------------------------------------------------

class TestRouteSteps:
    def test_steps_have_road_names(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        for step in result.steps:
            assert step.road_name  # non-empty string

    def test_steps_have_positive_length(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        for step in result.steps:
            assert step.length_m > 0

    def test_steps_have_positive_time(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        for step in result.steps:
            assert step.free_flow_time_s > 0
            assert step.actual_time_s >= step.free_flow_time_s

    def test_step_load_ratio_zero_when_no_loads(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        for step in result.steps:
            assert step.load_ratio == 0.0

    def test_steps_connect_from_to(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        assert len(result.steps) >= 1
        # First step starts near origin, last ends near destination
        first, last = result.steps[0], result.steps[-1]
        assert first.from_lat is not None
        assert last.to_lat is not None


# ---------------------------------------------------------------------------
# 3. Traffic weighting
# ---------------------------------------------------------------------------

class TestTrafficWeighting:
    def test_loaded_edge_has_higher_actual_time(self, router):
        # Load AB at 30% of peak — low enough that AB+BC (200m) is still
        # cheaper than the unloaded direct AC (350m, 35s), so route keeps AB.
        # AB+BC with load: 10*(1+0.9) + 10 = 29s < 35s ✓
        result_free = router.route(53.330, -6.270, 53.340, -6.250)
        result_traffic = router.route(
            53.330, -6.270, 53.340, -6.250,
            edge_loads={"AB": 30}, edge_peak=100,
        )
        ab_free = next(s for s in result_free.steps if s.edge_id == "AB")
        ab_traffic = next(s for s in result_traffic.steps if s.edge_id == "AB")
        assert ab_traffic.actual_time_s > ab_free.actual_time_s

    def test_congestion_factor_applied_correctly(self, router):
        # edge AB: length=100, speed=10 → ff_time=10s
        # at load_ratio=0.3: actual = 10 * (1 + 3.0 * 0.3) = 10 * 1.9 = 19s
        result = router.route(
            53.330, -6.270, 53.340, -6.250,
            edge_loads={"AB": 30}, edge_peak=100,
        )
        ab_step = next(s for s in result.steps if s.edge_id == "AB")
        expected_actual = ab_step.free_flow_time_s * (1 + _CONGESTION_FACTOR * 0.30)
        assert abs(ab_step.actual_time_s - expected_actual) < 0.5

    def test_heavily_loaded_short_route_forces_longer_path(self, router):
        # AB+BC both at max load (ratio=1.0):
        # AB cost = 100/10 * 4 = 40s, BC = 40s → total via B = 80s
        # AC (350m) free-flow: 350/10 = 35s  → AC becomes cheaper
        result = router.route(
            53.330, -6.270, 53.340, -6.250,
            edge_loads={"AB": 1, "BC": 1}, edge_peak=1,
        )
        edge_ids = [s.edge_id for s in result.steps]
        assert "AC" in edge_ids

    def test_traffic_delay_is_positive_when_loads_present(self, router):
        # Load all three edges (AB, BC, AC) at 30% so route stays via AB+BC
        # but incurs delay.  AB+BC loaded: 19+19=38s vs AC loaded: 66.5s → B.
        result = router.route(
            53.330, -6.270, 53.340, -6.250,
            edge_loads={"AB": 3, "BC": 3, "AC": 3}, edge_peak=10,
        )
        assert result.traffic_delay_s > 0

    def test_no_traffic_delay_when_no_loads(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        assert result.traffic_delay_s == 0.0

    def test_load_ratio_stored_on_step(self, router):
        # load_ratio = 30/100 = 0.3; route still goes via AB+BC (29s < 35s)
        result = router.route(
            53.330, -6.270, 53.340, -6.250,
            edge_loads={"AB": 30}, edge_peak=100,
        )
        ab_step = next(s for s in result.steps if s.edge_id == "AB")
        assert abs(ab_step.load_ratio - 0.30) < 0.01


# ---------------------------------------------------------------------------
# 4. Geometry
# ---------------------------------------------------------------------------

class TestGeometry:
    def test_geometry_non_empty_for_found_route(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        assert len(result.geometry) >= 2

    def test_geometry_contains_lat_lon_tuples(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        for point in result.geometry:
            lat, lon = point
            assert 53.0 < lat < 54.0
            assert -7.0 < lon < -6.0

    def test_geometry_empty_for_not_found(self, router):
        result = router.route(53.345, -6.240, 53.330, -6.270)
        assert result.geometry == []


# ---------------------------------------------------------------------------
# 5. Snap distances
# ---------------------------------------------------------------------------

class TestSnapDistance:
    def test_snap_distance_zero_when_on_junction(self, router, small_net):
        # Query exactly at jA's coordinates
        jA_lat, jA_lon = small_net.junctions["jA"]
        result = router.route(jA_lat, jA_lon, 53.340, -6.250)
        assert result.from_snap_m < 1.0  # essentially 0

    def test_snap_distances_are_non_negative(self, router):
        result = router.route(53.330, -6.270, 53.340, -6.250)
        assert result.from_snap_m >= 0
        assert result.to_snap_m >= 0


# ---------------------------------------------------------------------------
# 6. Haversine helper
# ---------------------------------------------------------------------------

class TestHaversine:
    def test_same_point_is_zero(self):
        d = DublinRouter._haversine_m(53.34, -6.26, 53.34, -6.26)
        assert d == pytest.approx(0.0, abs=0.1)

    def test_one_degree_lat_approx_111km(self):
        d = DublinRouter._haversine_m(53.0, -6.26, 54.0, -6.26)
        assert 110_000 < d < 112_000

    def test_symmetry(self):
        d1 = DublinRouter._haversine_m(53.33, -6.27, 53.34, -6.25)
        d2 = DublinRouter._haversine_m(53.34, -6.25, 53.33, -6.27)
        assert abs(d1 - d2) < 0.01
