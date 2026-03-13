from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from backend.api.serializers import to_jsonable
from backend.services.snapshot_service import AdapterCallSpec, SnapshotService
from backend.adapters.traffic_adapter import TrafficAdapter
from backend.fallback.cache import AdapterCache
from backend.fallback.predictor import PredictionResult
from backend.dublin_network.traffic_predictor import TrafficPredictor
from backend.dublin_network.router import DublinRouter
from backend.dublin_network.network_parser import get_network

traffic_bp = Blueprint("traffic", __name__)

_CACHE_TTL_SECONDS = 120.0

# Module-level singletons — loaded once when the app starts.
# TrafficPredictor reads all_trips.csv (~500k rows) on first import,
# so we keep a single instance rather than recreating per request.
_traffic_cache = AdapterCache()
_traffic_model = TrafficPredictor()
# Router shares the network singleton already loaded by the predictor
_router = DublinRouter()


def _make_predictor_fn():
    """
    Returns a callable with the signature expected by resolve_with_cache:
        (cached_snapshot) -> PredictionResult | None

    The cached_snapshot argument is ignored because our model predicts
    from historical trip data, not from the last known state.
    """
    def _predict(_cached_snapshot):
        now = datetime.now(timezone.utc)
        snapshot = _traffic_model.predict(now)
        return PredictionResult(
            snapshot=snapshot,
            generated_at=now,
            based_on=None,
            confidence=_traffic_model.confidence_at(now),
            reason="predicted_from_trip_histogram",
        )
    return _predict


@traffic_bp.get("/traffic")
def get_traffic():
    location = request.args.get("location", "dublin")
    try:
        radius_km = float(request.args.get("radius_km", "1.0"))
    except ValueError:
        radius_km = 1.0

    service = SnapshotService(
        adapter_specs=[
            AdapterCallSpec(
                adapter=TrafficAdapter(),
                kwargs={"radius_km": radius_km},
                cache_ttl_seconds=_CACHE_TTL_SECONDS,
            )
        ],
        cache=_traffic_cache,
        predictor=_make_predictor_fn(),
    )
    snapshot = service.build_snapshot(location=location)
    return jsonify(to_jsonable(snapshot))


@traffic_bp.get("/traffic/local-route")
def local_route():
    """
    Traffic-aware point-to-point driving route within Dublin using the SUMO
    road network (DCC.net.xml) and historical trip-load data.

    Query parameters
    ----------------
    from_lat, from_lon  : float  — origin WGS-84
    to_lat,   to_lon    : float  — destination WGS-84
    apply_traffic       : bool   — weight edges by current traffic load (default true)

    Response
    --------
    JSON with found, total_distance_m, total_actual_time_s, traffic_delay_s,
    geometry [[lat,lon],...], and a steps list with road name, length, time,
    and load_ratio per segment.
    """
    try:
        from_lat = float(request.args["from_lat"])
        from_lon = float(request.args["from_lon"])
        to_lat = float(request.args["to_lat"])
        to_lon = float(request.args["to_lon"])
    except (KeyError, ValueError):
        return jsonify({"error": "from_lat, from_lon, to_lat, to_lon are required floats"}), 400

    apply_traffic = request.args.get("apply_traffic", "true").lower() != "false"

    now = datetime.now(timezone.utc)
    edge_loads: dict = {}
    edge_peak: int = 1

    if apply_traffic:
        # Pull every edge that has any recorded load in this 15-min window
        from backend.dublin_network.traffic_predictor import _BIN_MINUTES, _BINS_PER_DAY
        bin_idx = (now.hour * 60 + now.minute) // _BIN_MINUTES % _BINS_PER_DAY
        edge_loads = dict(_traffic_model._edge_counts[bin_idx])
        edge_peak = _traffic_model._edge_peak or 1

    result = _router.route(
        from_lat=from_lat,
        from_lon=from_lon,
        to_lat=to_lat,
        to_lon=to_lon,
        edge_loads=edge_loads,
        edge_peak=edge_peak,
    )

    if not result.found:
        return jsonify({
            "found": False,
            "error": "No route found between those coordinates within the Dublin network.",
            "from_junction": result.from_junction,
            "to_junction": result.to_junction,
            "from_snap_m": result.from_snap_m,
            "to_snap_m": result.to_snap_m,
        }), 404

    steps_out = [
        {
            "road": s.road_name,
            "type": s.edge_type,
            "length_m": s.length_m,
            "free_flow_time_s": s.free_flow_time_s,
            "actual_time_s": s.actual_time_s,
            "load_ratio": s.load_ratio,
            "from": {"lat": s.from_lat, "lon": s.from_lon},
            "to": {"lat": s.to_lat, "lon": s.to_lon},
        }
        for s in result.steps
    ]

    congestion = _traffic_model.congestion_at(now)

    return jsonify({
        "found": True,
        "congestion_level": congestion,
        "traffic_applied": apply_traffic,
        "total_distance_m": result.total_distance_m,
        "total_distance_km": result.total_distance_km,
        "total_free_flow_time_s": result.total_free_flow_time_s,
        "total_actual_time_s": result.total_actual_time_s,
        "total_actual_time_min": result.total_actual_time_min,
        "traffic_delay_s": result.traffic_delay_s,
        "from_snap_m": result.from_snap_m,
        "to_snap_m": result.to_snap_m,
        "geometry": result.geometry,
        "steps": steps_out,
    })


def _convex_hull(points):
    """Graham scan convex hull on (lat, lon) points."""
    import math
    pts = list({(round(p[0], 6), round(p[1], 6)) for p in points})
    if len(pts) <= 3:
        return pts
    pivot = min(pts, key=lambda p: (p[0], p[1]))

    def _angle(p):
        return math.atan2(p[0] - pivot[0], p[1] - pivot[1])

    def _cross(o, a, b):
        return (a[1] - o[1]) * (b[0] - o[0]) - (a[0] - o[0]) * (b[1] - o[1])

    sorted_pts = sorted(pts, key=lambda p: (_angle(p),
                        (p[0] - pivot[0]) ** 2 + (p[1] - pivot[1]) ** 2))
    hull = []
    for p in sorted_pts:
        while len(hull) >= 2 and _cross(hull[-2], hull[-1], p) <= 0:
            hull.pop()
        hull.append(p)
    return hull


@traffic_bp.get("/traffic/network-nodes")
def network_nodes():
    """Return sampled road junction coordinates and convex hull for map debug."""
    net = get_network()
    step = int(request.args.get("step", 5))
    road_list = [jid for jid in net.road_nodes if jid in net.junctions]
    all_pts = [net.junctions[jid] for jid in road_list]

    nodes = [[lat, lon] for i, (lat, lon) in enumerate(all_pts) if i % step == 0]
    hull = [[lat, lon] for lat, lon in _convex_hull(all_pts)]

    return jsonify({
        "nodes": nodes,
        "hull": hull,
        "sampled": len(nodes),
        "total_road_junctions": len(road_list),
    })


@traffic_bp.get("/traffic/network-edges")
def network_edges():
    """Return sampled driveable edge shapes for coordinate alignment debugging."""
    net = get_network()
    step = int(request.args.get("step", 20))
    edges_out = []
    driveable = [ei for ei in net.edges.values() if ei.driveable]
    for i, ei in enumerate(driveable):
        if i % step != 0:
            continue
        if ei.shape_latlon:
            coords = [[lat, lon] for lat, lon in ei.shape_latlon]
        else:
            coords = [[ei.from_lat, ei.from_lon], [ei.to_lat, ei.to_lon]]
        edges_out.append({
            "name": ei.name if ei.name != ei.id else "",
            "type": ei.edge_type,
            "coords": coords,
        })
    return jsonify({"edges": edges_out, "sampled": len(edges_out), "total": len(driveable)})
