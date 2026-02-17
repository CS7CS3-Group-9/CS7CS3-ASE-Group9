import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import Set, Dict

from adapters.base_adapter import DataAdapter
from models.bus_models import BusStop, BusMetrics
from models.mobility_snapshot import MobilitySnapshot


class BusAdapter(DataAdapter):
    # Bounding box for Dublin
    DUBLIN_BBOX = {"min_lat": 53.2, "max_lat": 53.5, "min_lon": -6.5, "max_lon": -6.0}

    def __init__(self, gtfs_path: str):
        self.gtfs_path = Path(gtfs_path)
        print(f"[BusAdapter] Initialized. GTFS root: {self.gtfs_path / 'GTFS'}")

    def source_name(self) -> str:
        return "buses"

    def _is_within_dublin_bbox(self, lat: float, lon: float) -> bool:
        bbox = self.DUBLIN_BBOX
        return bbox["min_lat"] <= lat <= bbox["max_lat"] and bbox["min_lon"] <= lon <= bbox["max_lon"]

    def _count_stop_frequencies(self, dublin_stop_ids: Set[str]) -> Dict[str, int]:
        """
        Read stop_times.txt and count trips per stop, but only for stops
        that are in the dublin_stop_ids set.
        """
        stop_times_file = self.gtfs_path / "GTFS" / "stop_times.txt"
        frequencies = {}
        if not stop_times_file.exists():
            print(f"[Warning] {stop_times_file} not found. Cannot compute stop frequencies.")
            return frequencies

        print(f"[BusAdapter] Counting stop frequencies from {stop_times_file}...")
        line_count = 0
        with open(stop_times_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                line_count += 1
                stop_id = row.get("stop_id")
                if stop_id in dublin_stop_ids:
                    frequencies[stop_id] = frequencies.get(stop_id, 0) + 1

                # Optional progress indicator
                if line_count % 1_000_000 == 0:
                    print(f"[BusAdapter] Processed {line_count} stop_times rows...")

        print(f"[BusAdapter] Finished counting. Found frequencies for {len(frequencies)} stops.")
        return frequencies

    def fetch(self, city: str = "dublin") -> MobilitySnapshot:
        print(f"--- Fetching Bus Data for {city} (bounding box filter) ---")

        gtfs_dir = self.gtfs_path / "GTFS"
        stops_file = gtfs_dir / "stops.txt"

        all_stops = []
        dublin_stop_ids = set()  # collect IDs of stops that pass the bbox filter

        if stops_file.exists():
            with open(stops_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        lat = float(row["stop_lat"])
                        lon = float(row["stop_lon"])
                        if not self._is_within_dublin_bbox(lat, lon):
                            continue
                        stop_id = row["stop_id"]
                        dublin_stop_ids.add(stop_id)
                        stop = BusStop(stop_id=stop_id, name=row["stop_name"], lat=lat, longitude=lon)
                        all_stops.append(stop)
                    except (KeyError, ValueError) as e:
                        print(f"[Warning] Skipping stop {row.get('stop_id', 'unknown')}: {e}")
            print(f"[BusAdapter] Loaded {len(all_stops)} stops inside Dublin bounding box.")
        else:
            print(f"[Error] {stops_file} not found.")
            all_stops = []

        # Compute frequencies for the filtered stops
        frequencies = self._count_stop_frequencies(dublin_stop_ids)

        metrics = BusMetrics(stops=all_stops, stop_frequencies=frequencies, total_stops=len(all_stops))

        return MobilitySnapshot(buses=metrics, bikes=None, location=city, timestamp=datetime.now(timezone.utc))
