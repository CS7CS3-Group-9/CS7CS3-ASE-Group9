import csv
from pathlib import Path
from datetime import datetime, timezone
from typing import Set, Dict, Optional
from zoneinfo import ZoneInfo

from backend.adapters.base_adapter import DataAdapter
from backend.models.bus_models import BusStop, BusMetrics
from backend.analytics.bus_analytics import compute_average_waits_from_stop_times
from backend.models.mobility_snapshot import MobilitySnapshot


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
            return {}

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

        print(f"[BusAdapter] Finished counting. Found frequencies for {len(frequencies)} Dublin stops.")
        return frequencies

    def _parse_gtfs_time_to_seconds(self, raw_time: Optional[str]) -> Optional[int]:
        if not raw_time:
            return None
        parts = raw_time.strip().split(":")
        if len(parts) != 3:
            return None
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
        except ValueError:
            return None
        if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
            return None
        return hours * 3600 + minutes * 60 + seconds

    def _count_arrivals_within_hour(
        self, dublin_stop_ids: Set[str], now_local: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Count arrivals within the next hour, per stop_id, using stop_times.txt.
        Uses GTFS time format (HH:MM:SS), allowing hours > 24.
        """
        stop_times_file = self.gtfs_path / "GTFS" / "stop_times.txt"
        arrivals = {}
        if not stop_times_file.exists():
            print(f"[Warning] {stop_times_file} not found. Cannot compute arrivals within hour.")
            return arrivals

        if now_local is None:
            try:
                tz = ZoneInfo("Europe/Dublin")
            except Exception:
                tz = timezone.utc
            now_local = datetime.now(tz)
        now_sec = now_local.hour * 3600 + now_local.minute * 60 + now_local.second
        window_end = now_sec + 3600

        print(f"[BusAdapter] Counting arrivals within 1 hour from {stop_times_file}...")
        line_count = 0
        with open(stop_times_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                line_count += 1
                stop_id = row.get("stop_id")
                if stop_id not in dublin_stop_ids:
                    continue
                time_raw = row.get("arrival_time") or row.get("departure_time")
                arrival_sec = self._parse_gtfs_time_to_seconds(time_raw)
                if arrival_sec is None:
                    continue
                if now_sec <= arrival_sec <= window_end:
                    arrivals[stop_id] = arrivals.get(stop_id, 0) + 1

                if line_count % 1_000_000 == 0:
                    print(f"[BusAdapter] Processed {line_count} stop_times rows for arrivals...")

        print(f"[BusAdapter] Finished arrivals count. Found data for {len(arrivals)} stops.")
        return arrivals

    def fetch(self, location: str = "dublin", **kwargs) -> MobilitySnapshot:
        city = location
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
        arrivals_next_hour = self._count_arrivals_within_hour(dublin_stop_ids)
        stop_times_file = self.gtfs_path / "GTFS" / "stop_times.txt"
        if stop_times_file.exists():
            print(f"[BusAdapter] Computing average waits from {stop_times_file}...")
        else:
            print(f"[Warning] {stop_times_file} not found. Cannot compute average wait times.")
        avg_waits = compute_average_waits_from_stop_times(
            stop_times_file=stop_times_file,
            dublin_stop_ids=dublin_stop_ids,
            parse_time_fn=self._parse_gtfs_time_to_seconds,
        )
        if avg_waits:
            print(f"[BusAdapter] Finished average waits. Found data for {len(avg_waits)} stops.")

        metrics = BusMetrics(
            stops=all_stops,
            stop_frequencies=frequencies,
            stop_arrivals_next_hour=arrivals_next_hour,
            stop_avg_wait_min=avg_waits,
            total_stops=len(all_stops),
        )

        return MobilitySnapshot(buses=metrics, bikes=None, location=city, timestamp=datetime.now(timezone.utc))
