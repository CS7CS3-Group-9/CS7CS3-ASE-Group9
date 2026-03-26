from datetime import datetime, timezone
import csv

from backend.dublin_network.traffic_predictor import TrafficPredictor


def write_trips_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["depart_minutes", "from_edge", "to_edge"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def test_time_to_bin_and_counts(tmp_path):
    file = tmp_path / "trips.csv"
    # Create rows at 60 minutes -> bin 4 (hour 1, minute 0) if _BIN_MINUTES=15 -> 4th slot
    rows = [
        {"depart_minutes": "60", "from_edge": "e1", "to_edge": "e2"},
        {"depart_minutes": "60", "from_edge": "e1", "to_edge": "e3"},
    ]
    write_trips_csv(file, rows)

    p = TrafficPredictor(csv_path=str(file))
    # choose dt corresponding to minute 60 -> hour 1
    dt = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)
    assert p.trip_count_at(dt) == 2
    # top edges should include e1
    top = p.top_edges_at(dt, n=2)
    assert any(edge == "e1" for edge, cnt in top)


def test_build_incidents_no_top(tmp_path):
    # empty CSV (no rows) -> bins all zero
    file = tmp_path / "empty_trips.csv"
    write_trips_csv(file, [])
    p = TrafficPredictor(csv_path=str(file))
    dt = datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc)
    incidents = p._build_incidents("low", 0, p._time_to_bin(dt))
    assert isinstance(incidents, list)
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.from_location == "Dublin"
    assert inc.road == "Unknown"


def test_build_incidents_with_top(tmp_path):
    file = tmp_path / "trips2.csv"
    # create multiple rows in same bin with edges
    rows = [
        {"depart_minutes": "120", "from_edge": "edgeA", "to_edge": "edgeB"},
        {"depart_minutes": "120", "from_edge": "edgeA", "to_edge": "edgeC"},
        {"depart_minutes": "120", "from_edge": "edgeD", "to_edge": "edgeA"},
    ]
    write_trips_csv(file, rows)
    p = TrafficPredictor(csv_path=str(file), top_edges=3)
    dt = datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc)
    incidents = p._build_incidents("medium", p.trip_count_at(dt), p._time_to_bin(dt))
    assert isinstance(incidents, list)
    # should have at most top_edges incidents
    assert len(incidents) <= 3
    # incidents should reference an edge in our input
    assert any(inc.road.startswith("edge") for inc in incidents)
