import csv
from pathlib import Path
from datetime import datetime, timezone

from backend.adapters.base_adapter import DataAdapter
from backend.models.bus_models import BusStop, BusMetrics
from backend.models.mobility_snapshot import MobilitySnapshot


class BusAdapter(DataAdapter):
    # Bounding box for Dublin (approximate)
    DUBLIN_BBOX = {"min_lat": 53.2, "max_lat": 53.5, "min_lon": -6.5, "max_lon": -6.0}

    def __init__(self, gtfs_path: str):
        self.gtfs_path = Path(gtfs_path)
        print(f"[BusAdapter] Initialized. GTFS root: {self.gtfs_path / 'GTFS'}")

    def source_name(self) -> str:
        return "buses"

    def _is_within_dublin_bbox(self, lat: float, lon: float) -> bool:
        bbox = self.DUBLIN_BBOX
        return bbox["min_lat"] <= lat <= bbox["max_lat"] and bbox["min_lon"] <= lon <= bbox["max_lon"]

    def fetch(self, city: str = "dublin") -> MobilitySnapshot:
        print(f"--- Fetching Bus Data for {city} (bounding box filter) ---")

        gtfs_dir = self.gtfs_path / "GTFS"
        stops_file = gtfs_dir / "stops.txt"

        all_stops = []
        if stops_file.exists():
            with open(stops_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        lat = float(row["stop_lat"])
                        lon = float(row["stop_lon"])
                        if not self._is_within_dublin_bbox(lat, lon):
                            continue
                        stop = BusStop(stop_id=row["stop_id"], name=row["stop_name"], lat=lat, longitude=lon)
                        all_stops.append(stop)
                    except (KeyError, ValueError) as e:
                        print(f"[Warning] Skipping stop {row.get('stop_id', 'unknown')}: {e}")
            print(f"[BusAdapter] Loaded {len(all_stops)} stops inside Dublin bounding box.")
        else:
            print(f"[Error] {stops_file} not found.")
            all_stops = []

        metrics = BusMetrics(stops=all_stops, total_stops=len(all_stops))

        return MobilitySnapshot(
            buses=metrics,
            bikes=None,
            location=city,  # ✅ required by MobilitySnapshot
            timestamp=datetime.now(timezone.utc),
        )
