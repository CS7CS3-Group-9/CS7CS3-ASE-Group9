import pytest
from pathlib import Path

from backend.adapters.bus_adapter import BusAdapter
from backend.models.bus_models import BusStop, BusMetrics
from backend.models.mobility_snapshot import MobilitySnapshot

REAL_GTFS_DIR = r"C:\Users\Ruby\Documents\GitHub\CS7CS3-ASE-Group9\data\historical"


def test_source_name():
    adapter = BusAdapter(gtfs_path=REAL_GTFS_DIR)
    assert adapter.source_name() == "buses"


def test_fetch_dublin_stops_only():
    adapter = BusAdapter(gtfs_path=REAL_GTFS_DIR)
    snapshot = adapter.fetch("dublin")

    assert snapshot is not None
    assert isinstance(snapshot, MobilitySnapshot)
    assert isinstance(snapshot.buses, BusMetrics)

    metrics = snapshot.buses
    assert metrics.total_stops > 0, "Should have found stops in Dublin"
    assert len(metrics.stops) > 0, "Stops list should not be empty"

    # Verify all stops are inside Dublin bounding box
    bbox = adapter.DUBLIN_BBOX
    for stop in metrics.stops:
        assert bbox["min_lat"] <= stop.lat <= bbox["max_lat"], f"Latitude {stop.lat} out of Dublin bounds"
        assert bbox["min_lon"] <= stop.longitude <= bbox["max_lon"], f"Longitude {stop.longitude} out of Dublin bounds"

        # Also ensure no Waterford stop IDs (optional, but good sanity check)
        assert "8440" not in stop.stop_id, f"Waterford stop {stop.stop_id} found"

    # Basic structure checks
    for stop in metrics.stops:
        assert stop.stop_id, "Stop ID should not be empty"
        assert stop.name, "Stop name should not be empty"
        assert isinstance(stop.lat, float)
        assert isinstance(stop.longitude, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
