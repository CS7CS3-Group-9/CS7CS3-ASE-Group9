"""
DublinRouter
============
Traffic-aware Dijkstra routing on the DublinNetwork road graph.

Edge cost
---------
base_time = edge.length / edge.speed                 (free-flow travel time, s)
traffic_multiplier = 1 + CONGESTION_FACTOR * load_ratio
    where load_ratio = trips_on_edge / peak_trips_on_any_edge  ∈ [0, 1]

effective_time = base_time * traffic_multiplier

CONGESTION_FACTOR = 3.0 means that an edge at 100 % of peak load takes
4× its free-flow travel time — a realistic worst-case for Dublin's inner city.

Usage
-----
    from backend.dublin_network.router import DublinRouter
    from backend.dublin_network.network_parser import get_network

    router = DublinRouter(get_network())
    result = router.route(53.3498, -6.2603, 53.3418, -6.2675)
    # optionally pass edge_loads from TrafficPredictor.top_edges_at()
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .network_parser import DublinNetwork, get_network

# How much extra delay congested roads add.
# At load_ratio=1.0 → travel time is (1 + CONGESTION_FACTOR)× free-flow.
_CONGESTION_FACTOR = 3.0

# Maximum nodes to explore before giving up (guards against disconnected graph)
_MAX_NODES = 50_000


@dataclass
class RouteStep:
    """One road segment along the route."""
    edge_id: str
    road_name: str
    edge_type: str
    length_m: float
    free_flow_time_s: float
    actual_time_s: float      # free-flow adjusted for current traffic
    load_ratio: float         # 0.0–1.0 fraction of network peak
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float


@dataclass
class RouteResult:
    """Result returned by DublinRouter.route()."""
    found: bool
    from_junction: str
    to_junction: str
    total_distance_m: float
    total_free_flow_time_s: float
    total_actual_time_s: float       # includes traffic delay
    traffic_delay_s: float           # extra seconds due to congestion
    steps: List[RouteStep]
    geometry: List[Tuple[float, float]]   # [(lat, lon), ...] polyline
    # Nearest-junction snap distances in metres
    from_snap_m: float
    to_snap_m: float

    @property
    def total_distance_km(self) -> float:
        return round(self.total_distance_m / 1000, 3)

    @property
    def total_actual_time_min(self) -> float:
        return round(self.total_actual_time_s / 60, 1)


class DublinRouter:
    """
    Dijkstra router over the DublinNetwork driveable road graph.

    Parameters
    ----------
    network : DublinNetwork
        Pre-parsed road network (use network_parser.get_network() for the
        shared singleton so the XML is only parsed once).
    """

    def __init__(self, network: Optional[DublinNetwork] = None) -> None:
        self._net = network or get_network()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        edge_loads: Optional[Dict[str, int]] = None,
        edge_peak: int = 1,
    ) -> RouteResult:
        """
        Find the fastest driving route between two WGS-84 coordinates.

        Parameters
        ----------
        from_lat, from_lon : float
            Origin in WGS-84 degrees.
        to_lat, to_lon : float
            Destination in WGS-84 degrees.
        edge_loads : dict, optional
            {edge_id: trip_count} for the current time window, as returned
            by TrafficPredictor.top_edges_at().  Edges not in this dict are
            assumed unloaded (free-flow).
        edge_peak : int
            The maximum trip count across all edges in the network at this
            time window, used to normalise load_ratio.  Defaults to 1 (no
            normalisation needed when edge_loads is empty).

        Returns
        -------
        RouteResult
            .found=False if the destination is unreachable.
        """
        net = self._net
        loads = edge_loads or {}
        peak = max(edge_peak, 1)

        from_node = net.nearest_junction(from_lat, from_lon, restrict_to_road=True)
        to_node = net.nearest_junction(to_lat, to_lon, restrict_to_road=True)

        from_snap_m = self._haversine_m(from_lat, from_lon,
                                        *net.junctions[from_node])
        to_snap_m = self._haversine_m(to_lat, to_lon,
                                      *net.junctions[to_node])

        if from_node is None or to_node is None:
            return self._not_found(from_node or "", to_node or "",
                                   from_snap_m, to_snap_m)

        if from_node == to_node:
            return RouteResult(
                found=True,
                from_junction=from_node,
                to_junction=to_node,
                total_distance_m=0.0,
                total_free_flow_time_s=0.0,
                total_actual_time_s=0.0,
                traffic_delay_s=0.0,
                steps=[],
                geometry=[net.junctions[from_node]],
                from_snap_m=from_snap_m,
                to_snap_m=to_snap_m,
            )

        came_from, cost_so_far = self._dijkstra(
            from_node, to_node, loads, peak
        )

        if to_node not in came_from:
            return self._not_found(from_node, to_node, from_snap_m, to_snap_m)

        steps = self._reconstruct(came_from, to_node, loads, peak)
        total_dist = sum(s.length_m for s in steps)
        total_ff = sum(s.free_flow_time_s for s in steps)
        total_act = sum(s.actual_time_s for s in steps)

        # Build polyline using edge shape points for road-following geometry
        geom: List[Tuple[float, float]] = []
        for s in steps:
            shape = self._net.edges[s.edge_id].shape_latlon
            if shape:
                geom.extend(shape)
            else:
                geom.append((s.from_lat, s.from_lon))
                geom.append((s.to_lat, s.to_lon))

        return RouteResult(
            found=True,
            from_junction=from_node,
            to_junction=to_node,
            total_distance_m=round(total_dist, 1),
            total_free_flow_time_s=round(total_ff, 1),
            total_actual_time_s=round(total_act, 1),
            traffic_delay_s=round(total_act - total_ff, 1),
            steps=steps,
            geometry=geom,
            from_snap_m=round(from_snap_m, 1),
            to_snap_m=round(to_snap_m, 1),
        )

    # ------------------------------------------------------------------
    # Dijkstra core
    # ------------------------------------------------------------------

    def _edge_cost(self, edge_id: str, loads: Dict[str, int], peak: int) -> float:
        """Travel time in seconds, adjusted for current traffic load."""
        ei = self._net.edges[edge_id]
        load_ratio = loads.get(edge_id, 0) / peak
        multiplier = 1.0 + _CONGESTION_FACTOR * load_ratio
        return (ei.length / ei.speed) * multiplier

    def _dijkstra(
        self,
        start: str,
        goal: str,
        loads: Dict[str, int],
        peak: int,
    ) -> Tuple[Dict[str, Optional[Tuple[str, str]]], Dict[str, float]]:
        """
        Standard Dijkstra on self._net.graph.

        Returns
        -------
        came_from : {node: (prev_node, edge_id) | None}
        cost_so_far : {node: float}
        """
        came_from: Dict[str, Optional[Tuple[str, str]]] = {start: None}
        cost_so_far: Dict[str, float] = {start: 0.0}

        # heap: (cost, node)
        heap = [(0.0, start)]
        explored = 0

        while heap:
            current_cost, current = heapq.heappop(heap)
            explored += 1

            if current == goal:
                break
            if explored > _MAX_NODES:
                break
            if current_cost > cost_so_far.get(current, float("inf")) + 1e-9:
                continue  # stale entry

            for neighbour, edge_id in self._net.graph.get(current, []):
                new_cost = current_cost + self._edge_cost(edge_id, loads, peak)
                if new_cost < cost_so_far.get(neighbour, float("inf")):
                    cost_so_far[neighbour] = new_cost
                    came_from[neighbour] = (current, edge_id)
                    heapq.heappush(heap, (new_cost, neighbour))

        return came_from, cost_so_far

    def _reconstruct(
        self,
        came_from: Dict,
        goal: str,
        loads: Dict[str, int],
        peak: int,
    ) -> List[RouteStep]:
        """Walk came_from back to the start and return ordered steps."""
        steps = []
        node = goal
        while came_from[node] is not None:
            prev_node, edge_id = came_from[node]
            ei = self._net.edges[edge_id]
            load_ratio = loads.get(edge_id, 0) / peak
            multiplier = 1.0 + _CONGESTION_FACTOR * load_ratio
            ff_time = ei.length / ei.speed
            steps.append(RouteStep(
                edge_id=edge_id,
                road_name=ei.name,
                edge_type=ei.edge_type,
                length_m=round(ei.length, 1),
                free_flow_time_s=round(ff_time, 1),
                actual_time_s=round(ff_time * multiplier, 1),
                load_ratio=round(load_ratio, 3),
                from_lat=ei.from_lat,
                from_lon=ei.from_lon,
                to_lat=ei.to_lat,
                to_lon=ei.to_lon,
            ))
            node = prev_node
        steps.reverse()
        return steps

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Approximate distance in metres between two WGS-84 points."""
        import math
        R = 6_371_000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _not_found(
        from_node: str, to_node: str, from_snap_m: float, to_snap_m: float
    ) -> RouteResult:
        return RouteResult(
            found=False,
            from_junction=from_node,
            to_junction=to_node,
            total_distance_m=0.0,
            total_free_flow_time_s=0.0,
            total_actual_time_s=0.0,
            traffic_delay_s=0.0,
            steps=[],
            geometry=[],
            from_snap_m=from_snap_m,
            to_snap_m=to_snap_m,
        )
