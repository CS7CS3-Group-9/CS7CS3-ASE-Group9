"""
Tests for DublinNetwork (network_parser.py)
===========================================
Uses a minimal in-memory XML fixture so the real 115K-line DCC.net.xml
is never read during the test suite, keeping tests fast and self-contained.

Run: pytest backend/dublin_network/tests/test_network_parser.py -v
"""

import io
import pytest

from backend.dublin_network.network_parser import DublinNetwork

# ---------------------------------------------------------------------------
# Minimal SUMO net.xml fixture
# convBoundary / origBoundary are the real values from DCC.net.xml so the
# coordinate maths is exercised with the real constants.
# ---------------------------------------------------------------------------
_MINI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<net version="1.3" junctionCornerDetail="5" lefthand="true"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">

    <location netOffset="-677749.85,-5911444.78"
              convBoundary="0.00,0.00,7099.88,5359.80"
              origBoundary="-6.368224,53.318846,-6.186539,53.396212"
              projParameter="+proj=utm +zone=29 +ellps=WGS84"/>

    <!-- internal connector — must be ignored -->
    <edge id=":internal_0" function="internal">
        <lane id=":internal_0_0" index="0" speed="5.0" length="10.0"
              shape="100,100 110,110"/>
    </edge>

    <!-- driveable primary road A → B -->
    <edge id="edge_AB" from="jA" to="jB" name="Main Street"
          type="highway.primary" shape="100,100 200,200">
        <lane id="edge_AB_0" index="0" speed="13.89" length="141.42"
              shape="100,100 200,200"/>
    </edge>

    <!-- driveable secondary road B → C -->
    <edge id="edge_BC" from="jB" to="jC" name="Side Road"
          type="highway.secondary">
        <lane id="edge_BC_0" index="0" speed="11.11" length="100.0"
              shape="200,200 300,200"/>
    </edge>

    <!-- non-driveable footway — must not appear in graph -->
    <edge id="edge_foot" from="jA" to="jC" name="Footpath"
          type="highway.footway">
        <lane id="edge_foot_0" index="0" speed="1.39" length="50.0"
              shape="100,100 300,200"/>
    </edge>

    <!-- edge with no name — id should be used as fallback name -->
    <edge id="edge_noname" from="jC" to="jA" type="highway.residential">
        <lane id="edge_noname_0" index="0" speed="8.33" length="200.0"
              shape="300,200 100,100"/>
    </edge>

    <junction id="jA" type="priority" x="100.0" y="100.0"
              incLanes="" intLanes="" shape=""/>
    <junction id="jB" type="priority" x="200.0" y="200.0"
              incLanes="" intLanes="" shape=""/>
    <junction id="jC" type="priority" x="300.0" y="200.0"
              incLanes="" intLanes="" shape=""/>
    <!-- internal junction — must be excluded from self.junctions -->
    <junction id="jInternal" type="internal" x="150.0" y="150.0"
              incLanes="" intLanes="" shape=""/>
</net>
"""


@pytest.fixture(scope="module")
def net():
    """Parse the mini XML fixture once for the whole module."""
    # DublinNetwork._parse accepts any path, but we patch it to read from a
    # string buffer using xml.etree.ElementTree.iterparse's file-like support.
    import xml.etree.ElementTree as ET
    from unittest.mock import patch

    # Build the parsed tree from the in-memory string
    original_iterparse = ET.iterparse

    def fake_iterparse(source, events=("end",)):
        return original_iterparse(io.BytesIO(_MINI_XML.encode()), events=events)

    with patch("xml.etree.ElementTree.iterparse", side_effect=fake_iterparse):
        return DublinNetwork(xml_path="dummy_path_not_used")


# ---------------------------------------------------------------------------
# 1. Coordinate conversion
# ---------------------------------------------------------------------------

class TestLocalToLatlon:
    def test_origin_maps_to_sw_corner(self):
        # Correct UTM Zone 29N conversion for local (0, 0)
        lat, lon = DublinNetwork.local_to_latlon(0.0, 0.0)
        assert abs(lat - 53.322290) < 1e-4
        assert abs(lon - (-6.331191)) < 1e-4

    def test_max_corner_maps_to_ne_corner(self):
        # Correct UTM Zone 29N conversion for local (7099.88, 5359.80)
        lat, lon = DublinNetwork.local_to_latlon(7099.88, 5359.80)
        assert abs(lat - 53.367982) < 1e-4
        assert abs(lon - (-6.221596)) < 1e-4

    def test_midpoint_is_centre_of_dublin(self):
        lat, lon = DublinNetwork.local_to_latlon(7099.88 / 2, 5359.80 / 2)
        assert 53.31 < lat < 53.40
        assert -6.37 < lon < -6.18

    def test_x_increases_eastward(self):
        _, lon1 = DublinNetwork.local_to_latlon(1000, 1000)
        _, lon2 = DublinNetwork.local_to_latlon(2000, 1000)
        assert lon2 > lon1

    def test_y_increases_northward(self):
        lat1, _ = DublinNetwork.local_to_latlon(1000, 1000)
        lat2, _ = DublinNetwork.local_to_latlon(1000, 2000)
        assert lat2 > lat1

    def test_result_rounded_to_6dp(self):
        lat, lon = DublinNetwork.local_to_latlon(1234.56, 2345.67)
        assert len(str(lat).split(".")[-1]) <= 6
        assert len(str(lon).split(".")[-1]) <= 6


# ---------------------------------------------------------------------------
# 2. Junction parsing
# ---------------------------------------------------------------------------

class TestJunctions:
    def test_known_junctions_present(self, net):
        assert "jA" in net.junctions
        assert "jB" in net.junctions
        assert "jC" in net.junctions

    def test_internal_junction_excluded(self, net):
        assert "jInternal" not in net.junctions

    def test_junction_lat_in_dublin_range(self, net):
        for jid, (lat, lon) in net.junctions.items():
            assert 53.31 < lat < 53.40, f"{jid} lat out of range: {lat}"
            assert -6.37 < lon < -6.18, f"{jid} lon out of range: {lon}"

    def test_junctions_have_correct_relative_order(self, net):
        # jB is further east/north than jA (x=200,y=200 vs x=100,y=100)
        lat_a, lon_a = net.junctions["jA"]
        lat_b, lon_b = net.junctions["jB"]
        assert lat_b > lat_a
        assert lon_b > lon_a


# ---------------------------------------------------------------------------
# 3. Edge parsing
# ---------------------------------------------------------------------------

class TestEdges:
    def test_driveable_edges_present(self, net):
        assert "edge_AB" in net.edges
        assert "edge_BC" in net.edges
        assert "edge_noname" in net.edges

    def test_internal_edge_excluded(self, net):
        assert ":internal_0" not in net.edges

    def test_footway_excluded_from_graph_but_present_in_edges(self, net):
        # We store all edges (for coordinate lookup), but only driveable in graph
        assert "edge_foot" in net.edges
        assert not net.edges["edge_foot"].driveable

    def test_edge_name_populated(self, net):
        assert net.edges["edge_AB"].name == "Main Street"
        assert net.edges["edge_BC"].name == "Side Road"

    def test_edge_no_name_falls_back_to_id(self, net):
        assert net.edges["edge_noname"].name == "edge_noname"

    def test_edge_speed_from_lane(self, net):
        assert abs(net.edges["edge_AB"].speed - 13.89) < 0.01
        assert abs(net.edges["edge_BC"].speed - 11.11) < 0.01

    def test_edge_length_from_lane(self, net):
        assert abs(net.edges["edge_AB"].length - 141.42) < 0.1

    def test_edge_type_stored(self, net):
        assert net.edges["edge_AB"].edge_type == "highway.primary"
        assert net.edges["edge_BC"].edge_type == "highway.secondary"
        assert net.edges["edge_foot"].edge_type == "highway.footway"

    def test_driveable_flag_true_for_road(self, net):
        assert net.edges["edge_AB"].driveable is True

    def test_driveable_flag_false_for_footway(self, net):
        assert net.edges["edge_foot"].driveable is False

    def test_edge_from_to_nodes(self, net):
        assert net.edges["edge_AB"].from_node == "jA"
        assert net.edges["edge_AB"].to_node == "jB"

    def test_edge_coordinates_in_dublin_range(self, net):
        ei = net.edges["edge_AB"]
        for lat in (ei.from_lat, ei.mid_lat, ei.to_lat):
            assert 53.31 < lat < 53.40
        for lon in (ei.from_lon, ei.mid_lon, ei.to_lon):
            assert -6.37 < lon < -6.18


# ---------------------------------------------------------------------------
# 4. Graph structure
# ---------------------------------------------------------------------------

class TestGraph:
    def test_driveable_edges_in_graph(self, net):
        # jA should have edge_AB in its adjacency list
        neighbours = [eid for _, eid in net.graph.get("jA", [])]
        assert "edge_AB" in neighbours

    def test_footway_not_in_graph(self, net):
        neighbours = [eid for _, eid in net.graph.get("jA", [])]
        assert "edge_foot" not in neighbours

    def test_graph_direction(self, net):
        # edge_AB goes jA→jB; jB should have edge_BC, not edge_AB
        b_neighbours = [eid for _, eid in net.graph.get("jB", [])]
        assert "edge_BC" in b_neighbours
        assert "edge_AB" not in b_neighbours

    def test_road_nodes_populated(self, net):
        assert "jA" in net.road_nodes
        assert "jB" in net.road_nodes
        assert "jC" in net.road_nodes

    def test_internal_junction_not_in_road_nodes(self, net):
        assert "jInternal" not in net.road_nodes


# ---------------------------------------------------------------------------
# 5. Nearest junction
# ---------------------------------------------------------------------------

class TestNearestJunction:
    def test_returns_closest_node(self, net):
        # Place a query point very close to jA's coordinates
        jA_lat, jA_lon = net.junctions["jA"]
        result = net.nearest_junction(jA_lat + 0.0001, jA_lon + 0.0001)
        assert result == "jA"

    def test_returns_closest_node_to_jC(self, net):
        jC_lat, jC_lon = net.junctions["jC"]
        result = net.nearest_junction(jC_lat, jC_lon)
        assert result == "jC"

    def test_restrict_to_road_excludes_internal_junction(self, net):
        # Internal junction not in road_nodes; nearest_junction should still work
        result = net.nearest_junction(53.33, -6.30, restrict_to_road=True)
        assert result in net.road_nodes

    def test_returns_none_when_no_junctions(self):
        empty_net = object.__new__(DublinNetwork)
        empty_net.junctions = {}
        empty_net.road_nodes = set()
        assert empty_net.nearest_junction(53.3, -6.2) is None

    def test_edge_latlon_returns_midpoint(self, net):
        result = net.edge_latlon("edge_AB")
        assert result is not None
        lat, lon = result
        assert 53.31 < lat < 53.40
        assert -6.37 < lon < -6.18

    def test_edge_latlon_returns_none_for_unknown(self, net):
        assert net.edge_latlon("nonexistent_edge") is None
