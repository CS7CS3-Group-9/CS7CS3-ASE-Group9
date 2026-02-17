import pytest
from pathlib import Path

from adapters.bus_adapter import BusAdapter
from models.bus_models import BusStop, BusMetrics
from models.mobility_snapshot import MobilitySnapshot

# Get the directory of this test file
TEST_DIR = Path(__file__).parent
# Go up to project root (three levels: tests/ -> adapters/ -> backend/ -> project root)
PROJECT_ROOT = TEST_DIR.parent.parent.parent
# Build path to data/historical
REAL_GTFS_DIR = PROJECT_ROOT / "data" / "historical"


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

    assert hasattr(metrics, "stop_frequencies")
    assert isinstance(metrics.stop_frequencies, dict)
    # At least one stop should have a frequency > 0 (assuming stop_times exists)
    if metrics.stops:
        any_freq = any(metrics.stop_frequencies.get(stop.stop_id, 0) > 0 for stop in metrics.stops)
        assert any_freq, "No stop frequency > 0 found – is stop_times.txt missing or empty?"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
