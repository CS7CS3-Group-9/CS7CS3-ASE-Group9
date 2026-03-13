"""
DublinNetwork
=============
Parses DCC.net.xml (SUMO road network) into a lightweight directed graph
suitable for traffic-aware routing and real-coordinate incident mapping.

Coordinate system
-----------------
DCC.net.xml stores positions in SUMO local coordinates (metres), generated
by SUMO netconvert with UTM Zone 29N projection (WGS84 datum).

The <location> element contains:
    netOffset="-677749.85,-5911444.78"
    projParameter="+proj=utm +zone=29 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"

The correct conversion is:
    utm_easting  = local_x - netOffset_x  =  local_x + 677749.85
    utm_northing = local_y - netOffset_y  =  local_y + 5911444.78
then apply the standard UTM Zone 29N inverse projection to get WGS-84.
"""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_XML_PATH = os.path.join(os.path.dirname(__file__), "DCC.net.xml")

# ---------------------------------------------------------------------------
# UTM Zone 29N projection constants (from <location> element in DCC.net.xml)
# ---------------------------------------------------------------------------
# netOffset converts local SUMO coords to UTM:  utm = local - netOffset
_NET_OFFSET_X = -677749.85   # utm_easting  = local_x + 677749.85
_NET_OFFSET_Y = -5911444.78  # utm_northing = local_y + 5911444.78
_UTM_ZONE = 29               # UTM zone (central meridian = -9°)

# WGS-84 ellipsoid parameters
_A  = 6378137.0              # semi-major axis, m
_F  = 1 / 298.257223563      # flattening
_B  = _A * (1 - _F)
_E2 = 2 * _F - _F ** 2       # first eccentricity squared
_EP2 = _E2 / (1 - _E2)       # second eccentricity squared
_K0 = 0.9996                 # UTM scale factor
_LON0 = math.radians((_UTM_ZONE - 1) * 6 - 180 + 3)  # central meridian = -9°

# Road types considered driveable for car routing
_DRIVEABLE_TYPES = {
    "highway.motorway",       "highway.motorway_link",
    "highway.trunk",          "highway.trunk_link",
    "highway.primary",        "highway.primary_link",
    "highway.secondary",      "highway.secondary_link",
    "highway.tertiary",       "highway.tertiary_link",
    "highway.residential",    "highway.living_street",
    "highway.unclassified",   "highway.unsurfaced",
    "highway.service",
}

# Free-flow speed multipliers by road type (relative to tagged speed)
# Higher priority roads tend to flow faster when not congested
_TYPE_SPEED_FACTOR = {
    "highway.motorway":      1.0,
    "highway.trunk":         0.95,
    "highway.primary":       0.85,
    "highway.secondary":     0.80,
    "highway.tertiary":      0.75,
    "highway.residential":   0.65,
    "highway.unclassified":  0.65,
    "highway.service":       0.50,
    "highway.living_street": 0.40,
}


@dataclass
class EdgeInfo:
    id: str
    from_node: str
    to_node: str
    name: str          # human-readable street name (may equal id if absent)
    edge_type: str     # e.g. "highway.residential"
    speed: float       # m/s free-flow (from lane element)
    length: float      # metres (from lane element)
    mid_lat: float
    mid_lon: float
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    driveable: bool
    shape_latlon: List[Tuple[float, float]] = field(default_factory=list)


class DublinNetwork:
    """
    Directed road graph parsed once from DCC.net.xml.

    Attributes
    ----------
    junctions : dict {junction_id: (lat, lon)}
    edges     : dict {edge_id: EdgeInfo}
    graph     : dict {from_node: [(to_node, edge_id), ...]}  — driveable only
    road_nodes: set  — all junction IDs that touch at least one driveable edge
    """

    def __init__(self, xml_path: str = _XML_PATH) -> None:
        self.junctions: Dict[str, Tuple[float, float]] = {}
        self.edges: Dict[str, EdgeInfo] = {}
        self.graph: Dict[str, List[Tuple[str, str]]] = {}
        self.road_nodes: set = set()
        self._parse(xml_path)

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    @staticmethod
    def local_to_latlon(x: float, y: float) -> Tuple[float, float]:
        """Convert SUMO local (x, y) metres to WGS-84 (lat, lon).

        Uses the proper UTM Zone 29N inverse projection via the netOffset
        stored in DCC.net.xml, instead of a simple bounding-box interpolation
        (which introduced ~1.4 km of error at the centre of the network).
        """
        # Step 1 — local SUMO coords → UTM Zone 29N (metres)
        E = x - _NET_OFFSET_X   # = x + 677749.85
        N = y - _NET_OFFSET_Y   # = y + 5911444.78

        # Step 2 — UTM inverse projection (Karney / Bowring series)
        x_utm = E - 500_000.0   # remove false easting
        M = N / _K0
        e1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
        mu = M / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256))
        phi1 = (mu
                + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
                + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
                + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
                + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
        sin_p = math.sin(phi1)
        cos_p = math.cos(phi1)
        tan_p = math.tan(phi1)
        N1 = _A / math.sqrt(1 - _E2 * sin_p ** 2)
        T1 = tan_p ** 2
        C1 = _EP2 * cos_p ** 2
        R1 = _A * (1 - _E2) / (1 - _E2 * sin_p ** 2) ** 1.5
        D = x_utm / (N1 * _K0)
        lat = phi1 - (N1 * tan_p / R1) * (
            D ** 2 / 2
            - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * _EP2) * D ** 4 / 24
            + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * _EP2 - 3 * C1 ** 2) * D ** 6 / 720)
        lon = (D
               - (1 + 2 * T1 + C1) * D ** 3 / 6
               + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * _EP2 + 24 * T1 ** 2) * D ** 5 / 120
               ) / cos_p
        lat_deg = round(math.degrees(lat), 6)
        lon_deg = round(math.degrees(lon) + math.degrees(_LON0), 6)
        return lat_deg, lon_deg

    # ------------------------------------------------------------------
    # XML parsing (single iterparse pass)
    # ------------------------------------------------------------------

    def _parse(self, xml_path: str) -> None:
        """
        Parse junctions and edges in one pass.

        Junctions appear after edges in the SUMO net file, so we collect raw
        edge data first and resolve coordinates in a second post-processing
        step once all junctions are known.
        """
        # Raw edge data before coordinate resolution
        # {edge_id: (from_node, to_node, name, etype, speed, length, shape_str)}
        raw_edges: Dict[str, tuple] = {}

        context = ET.iterparse(xml_path, events=("end",))
        for _, elem in context:
            tag = elem.tag

            if tag == "junction":
                jid = elem.get("id", "")
                jtype = elem.get("type", "")
                # Skip internal connector nodes
                if jtype not in ("internal", "dead_end") and jid:
                    try:
                        x = float(elem.get("x", 0))
                        y = float(elem.get("y", 0))
                        self.junctions[jid] = self.local_to_latlon(x, y)
                    except ValueError:
                        pass
                elem.clear()

            elif tag == "edge":
                if elem.get("function") == "internal":
                    elem.clear()
                    continue

                eid = elem.get("id", "")
                from_node = elem.get("from", "")
                to_node = elem.get("to", "")
                if not eid or not from_node or not to_node:
                    elem.clear()
                    continue

                name = elem.get("name", "")
                etype = elem.get("type", "")

                lane = elem.find("lane")
                speed = float(lane.get("speed", 13.89)) if lane is not None else 13.89
                length = float(lane.get("length", 50.0)) if lane is not None else 50.0
                # Lane shape is more accurate than edge shape for road geometry
                shape_str = (lane.get("shape", "") if lane is not None else "") or elem.get("shape", "")

                raw_edges[eid] = (from_node, to_node, name, etype, speed, length, shape_str)
                elem.clear()

        # ------------------------------------------------------------------
        # Resolve edge coordinates now that all junctions are loaded
        # ------------------------------------------------------------------
        for eid, (from_node, to_node, name, etype, speed, length, shape_str) in raw_edges.items():
            from_lat, from_lon = self.junctions.get(from_node, (53.345, -6.276))
            to_lat, to_lon = self.junctions.get(to_node, (53.345, -6.276))

            # Parse full shape into WGS-84 points for road-following geometry
            shape_latlon: List[Tuple[float, float]] = []
            if shape_str:
                try:
                    for p in shape_str.strip().split():
                        sx, sy = p.split(",")
                        shape_latlon.append(self.local_to_latlon(float(sx), float(sy)))
                except (IndexError, ValueError):
                    shape_latlon = []

            # Mid-point: prefer shape midpoint, fall back to junction average
            mid_lat = mid_lon = None
            if shape_latlon:
                mid = shape_latlon[len(shape_latlon) // 2]
                mid_lat, mid_lon = mid
            if mid_lat is None:
                mid_lat = round((from_lat + to_lat) / 2, 6)
                mid_lon = round((from_lon + to_lon) / 2, 6)

            driveable = etype in _DRIVEABLE_TYPES
            ei = EdgeInfo(
                id=eid,
                from_node=from_node,
                to_node=to_node,
                name=name if name else eid,
                edge_type=etype,
                speed=speed,
                length=length,
                mid_lat=mid_lat,
                mid_lon=mid_lon,
                from_lat=from_lat,
                from_lon=from_lon,
                to_lat=to_lat,
                to_lon=to_lon,
                driveable=driveable,
                shape_latlon=shape_latlon,
            )
            self.edges[eid] = ei

            if driveable:
                self.graph.setdefault(from_node, []).append((to_node, eid))
                self.road_nodes.add(from_node)
                self.road_nodes.add(to_node)

        # Some edges reference junctions that were excluded (internal/dead_end
        # type) or are simply absent from the XML.  Remove them so that
        # nearest_junction never tries to look up a missing key.
        self.road_nodes = {jid for jid in self.road_nodes if jid in self.junctions}

    # ------------------------------------------------------------------
    # Spatial helpers
    # ------------------------------------------------------------------

    def nearest_junction(self, lat: float, lon: float,
                         restrict_to_road: bool = True) -> Optional[str]:
        """
        Return the ID of the junction closest to (lat, lon).

        Parameters
        ----------
        restrict_to_road : bool
            If True (default), only consider junctions that touch at least
            one driveable edge — ensures the start/end of a route sits on
            a navigable road.
        """
        candidates = self.road_nodes if restrict_to_road else self.junctions.keys()
        best_id, best_dist_sq = None, float("inf")
        for jid in candidates:
            if jid not in self.junctions:
                continue
            jlat, jlon = self.junctions[jid]
            # Approximate planar distance (metres squared)
            dlat = (lat - jlat) * 111_000
            dlon = (lon - jlon) * 72_000   # ~cos(53.3°) ≈ 0.60 → 111000*0.60≈72000
            d_sq = dlat * dlat + dlon * dlon
            if d_sq < best_dist_sq:
                best_dist_sq = d_sq
                best_id = jid
        return best_id

    def edge_latlon(self, edge_id: str) -> Optional[Tuple[float, float]]:
        """Return (lat, lon) midpoint for an edge, or None if unknown."""
        ei = self.edges.get(edge_id)
        if ei is None:
            return None
        return ei.mid_lat, ei.mid_lon


# ---------------------------------------------------------------------------
# Module-level lazy singleton — loaded once, shared by predictor and router
# ---------------------------------------------------------------------------

_network_singleton: Optional[DublinNetwork] = None


def get_network() -> DublinNetwork:
    """Return the module-level DublinNetwork singleton, loading it on first call."""
    global _network_singleton
    if _network_singleton is None:
        _network_singleton = DublinNetwork()
    return _network_singleton
