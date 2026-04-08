import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from backend.adapters.bus_adapter import BusAdapter


def test_load_precomputed_metrics(tmp_path):
    gtfs = tmp_path / "GTFS"
    gtfs.mkdir()
    stops_file = gtfs / "stops.txt"
    stop_times_file = gtfs / "stop_times.txt"
    stops_file.write_text("stop_id,name,lat,lon\n1,One,53.35,-6.26\n2,Two,53.36,-6.27\n")
    stop_times_file.write_text("trip,arrival_time,stop_id\nt1,12:00:00,1\n")

    # compute mtimes to place in precomputed payload
    stops_mtime = stops_file.stat().st_mtime
    stop_times_mtime = stop_times_file.stat().st_mtime

    # figure current hour in Europe/Dublin
    try:
        now_local = datetime.now(ZoneInfo("Europe/Dublin"))
    except Exception:
        now_local = datetime.now(timezone.utc)
    current_hour = int(now_local.hour)

    arrivals_by_hour = {
        "1": [0] * 24,
        "2": [0] * 24,
    }
    arrivals_by_hour["1"][current_hour] = 5
    # include a non-integer value for station 2 at that hour to exercise exception path
    arrivals_by_hour["2"][current_hour] = "bad"

    payload = {
        "meta": {"stops_mtime": float(stops_mtime), "stop_times_mtime": float(stop_times_mtime)},
        "metrics": {
            "stops": [
                {"stop_id": "1", "name": "One", "lat": 53.35, "lon": -6.26},
                {"stop_id": None, "name": "Bad", "lat": None, "lon": None},
            ],
            "arrivals_by_hour": arrivals_by_hour,
            "stop_frequencies": {"1": 10},
            "stop_avg_wait_min": {"1": 3},
            "total_stops": 1,
            "total_routes": 2,
        },
    }

    precomputed = gtfs / "bus_metrics.json"
    precomputed.write_text(json.dumps(payload))

    b = BusAdapter(gtfs_path=str(tmp_path))
    snapshot = b._load_precomputed_metrics(stops_file, stop_times_file)
    assert snapshot is not None
    assert snapshot.buses.total_stops >= 1
    # stop_arrivals_next_hour should include integer for stop '1'
    assert str(1) in snapshot.buses.stop_arrivals_next_hour or "1" in snapshot.buses.stop_arrivals_next_hour
