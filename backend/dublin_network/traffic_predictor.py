"""
TrafficPredictor
================
Predicts Dublin traffic conditions from SUMO simulation trip data.

Source data: all_trips.csv — 500 000 simulated vehicle trips with
departure times in minutes from midnight covering a full 24 h period.

Strategy
--------
1. At init, load the CSV and build two structures per 15-minute bin (96 total):
   - trip count histogram  (_bins[96])
   - from_edge frequency Counter (_edge_counts[96])
2. Given a datetime, map it to the correct bin and derive:
   - congestion level  ("low" / "medium" / "high")
   - TrafficIncident list using the top N busiest road segments from the
     actual simulation data for that time window
3. Return a MobilitySnapshot so this adapter slots directly into the
   existing fallback/resolver pipeline.

Integration (wired automatically in traffic.py)
-----------------------------------------------
The traffic endpoint creates a module-level TrafficPredictor singleton and
passes a predictor function to SnapshotService / resolve_with_cache.
When TomTom fails AND there is nothing cached, the predictor is called and
returns a predicted snapshot from the trip histogram.
"""

from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import datetime, timezone

from backend.adapters.base_adapter import DataAdapter
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.models.traffic_models import TrafficIncident
from backend.dublin_network.network_parser import get_network

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_CSV_PATH = os.path.join(os.path.dirname(__file__), "all_trips.csv")

# 15-minute bins → 96 slots per 24 h
_BIN_MINUTES = 15
_BINS_PER_DAY = (24 * 60) // _BIN_MINUTES  # 96

# How many top road segments to include per prediction
_TOP_EDGES = 5

# Congestion thresholds (fraction of daily peak bin)
_HIGH_THRESHOLD = 0.70
_MEDIUM_THRESHOLD = 0.35

# Dublin city-centre anchor coordinates
_DUBLIN_LAT = 53.3498
_DUBLIN_LON = -6.2603

# Per-congestion-level parameters for synthesised incidents
_LEVEL_CONFIG = {
    #               severity     delay_min  length_m
    "high":   dict(severity="Major",    delay_min=15.0, length_m=2000),
    "medium": dict(severity="Moderate", delay_min=7.0,  length_m=1000),
    "low":    dict(severity="Minor",    delay_min=2.0,  length_m=400),
}


# ---------------------------------------------------------------------------
# TrafficPredictor
# ---------------------------------------------------------------------------

class TrafficPredictor(DataAdapter):
    """
    Predicts Dublin traffic conditions from a SUMO trip-departure histogram.

    At init it reads all_trips.csv once and builds:
      - _bins[96]         — total trips per 15-min slot
      - _edge_counts[96]  — Counter of from_edge occurrences per slot

    At prediction time it looks up the current slot, takes the top N
    busiest from_edge segments, and emits one TrafficIncident per segment
    with severity calibrated to the historical congestion level.

    Parameters
    ----------
    csv_path : str
        Path to all_trips.csv. Defaults to the file bundled alongside
        this module.
    top_edges : int
        Maximum number of road segments to include per prediction.
    """

    def __init__(
        self,
        csv_path: str = _CSV_PATH,
        top_edges: int = _TOP_EDGES,
    ) -> None:
        self._csv_path = csv_path
        self._top_edges = top_edges
        self._bins, self._edge_counts = self._load_data()
        self._peak: int = max(self._bins) if any(self._bins) else 1
        # Busiest single edge across all bins — used for per-segment congestion scoring
        self._edge_peak: int = max(
            (count for c in self._edge_counts for count in c.values()),
            default=1,
        )
        # Load the road network for real edge coordinates (lazy — parsed once)
        try:
            self._network = get_network()
        except Exception:
            self._network = None

    # ------------------------------------------------------------------
    # DataAdapter interface
    # ------------------------------------------------------------------

    def source_name(self) -> str:
        return "traffic_predicted"

    def fetch(self, location: str = "dublin", radius_km: float = 5.0) -> MobilitySnapshot:
        """Fetch a predicted snapshot for the current wall-clock time."""
        return self.predict(datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Public prediction API
    # ------------------------------------------------------------------

    def predict(self, dt: datetime) -> MobilitySnapshot:
        """
        Return a predicted MobilitySnapshot for *dt*.

        The snapshot contains TrafficIncident objects for the top N
        busiest road segments at this time of day, with severity and
        delay calibrated to the historical congestion level.
        """
        bin_idx = self._time_to_bin(dt)
        trip_count = self._bins[bin_idx]
        congestion = self._congestion_level(trip_count)
        incidents = self._build_incidents(congestion, trip_count, bin_idx)

        return MobilitySnapshot(
            timestamp=dt,
            location="dublin",
            traffic=incidents,
            source_status={"traffic": "predicted"},
        )

    def congestion_at(self, dt: datetime) -> str:
        """Return 'low', 'medium', or 'high' for the given datetime."""
        return self._congestion_level(self._bins[self._time_to_bin(dt)])

    def confidence_at(self, dt: datetime) -> float:
        """
        Confidence in the prediction, scaled by how busy the bin is
        relative to the daily peak.  Night bins with zero trips return
        0.5 — we know it's quiet but have no direct evidence.
        """
        count = self._bins[self._time_to_bin(dt)]
        if count == 0:
            return 0.5
        return min(1.0, count / self._peak)

    def trip_count_at(self, dt: datetime) -> int:
        """Return the raw simulated trip count for the 15-min bin of *dt*."""
        return self._bins[self._time_to_bin(dt)]

    def top_edges_at(self, dt: datetime, n: int | None = None) -> list[tuple[str, int]]:
        """Return [(edge_id, count), ...] for the N busiest segments at *dt*."""
        n = n or self._top_edges
        return self._edge_counts[self._time_to_bin(dt)].most_common(n)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_data(self) -> tuple[list[int], list[Counter]]:
        """
        Single-pass CSV parse.  Builds both the trip-count histogram and
        per-bin edge load counters.

        Edge load is counted on both from_edge and to_edge for each trip,
        so an edge that is a popular origin AND a popular destination
        accumulates a higher load score — reflecting real congestion pressure
        from vehicles both departing and arriving on that segment.
        """
        bins: list[int] = [0] * _BINS_PER_DAY
        edge_counts: list[Counter] = [Counter() for _ in range(_BINS_PER_DAY)]

        with open(self._csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    minutes = float(row["depart_minutes"])
                    idx = int(minutes // _BIN_MINUTES) % _BINS_PER_DAY
                    bins[idx] += 1
                    edge_counts[idx][row["from_edge"]] += 1
                    edge_counts[idx][row["to_edge"]] += 1
                except (ValueError, KeyError):
                    continue

        return bins, edge_counts

    @staticmethod
    def _time_to_bin(dt: datetime) -> int:
        minutes_since_midnight = dt.hour * 60 + dt.minute
        return int(minutes_since_midnight // _BIN_MINUTES) % _BINS_PER_DAY

    def _congestion_level(self, trip_count: int) -> str:
        ratio = trip_count / self._peak if self._peak > 0 else 0.0
        if ratio >= _HIGH_THRESHOLD:
            return "high"
        if ratio >= _MEDIUM_THRESHOLD:
            return "medium"
        return "low"

    def _edge_lat_lon(self, edge_id: str) -> tuple[float, float]:
        """
        Return the real WGS-84 mid-point of an edge from the parsed road
        network.  Falls back to a hash-based pseudo-position if the edge
        is not found in the network (e.g. internal connector edges).
        """
        if self._network is not None:
            pos = self._network.edge_latlon(edge_id)
            if pos is not None:
                return pos
        # Fallback: deterministic pseudo-position inside Dublin bounds
        h1 = hash(edge_id) & 0xFFFF
        h2 = hash(edge_id + "_lon") & 0xFFFF
        lat = _DUBLIN_LAT + (h1 / 0xFFFF - 0.5) * 0.08
        lon = _DUBLIN_LON + (h2 / 0xFFFF - 0.5) * 0.12
        return round(lat, 6), round(lon, 6)

    def _build_incidents(
        self, congestion: str, trip_count: int, bin_idx: int
    ) -> list[TrafficIncident]:
        """
        Build one TrafficIncident per top busy road segment in this bin.

        Each segment gets its own congestion level derived from its individual
        load score (its trip count relative to the busiest single edge across
        the whole dataset), so a moderately-busy window can still contain a
        mix of high/medium/low segments.
        """
        top = self._edge_counts[bin_idx].most_common(self._top_edges)

        if not top:
            # Night / out-of-simulation window — no edge data
            cfg = _LEVEL_CONFIG[congestion]
            return [
                TrafficIncident(
                    category="Jam",
                    severity=cfg["severity"],
                    description=f"Predicted {congestion} congestion (no segment data for this window)",
                    from_location="Dublin",
                    to_location="Dublin Centre",
                    road="Unknown",
                    length_meters=cfg["length_m"],
                    delay_seconds=round(cfg["delay_min"] * 60),
                    delay_minutes=cfg["delay_min"],
                    latitude=_DUBLIN_LAT,
                    longitude=_DUBLIN_LON,
                )
            ]

        incidents: list[TrafficIncident] = []
        for edge_id, edge_load in top:
            # Per-segment congestion level based on that edge's own load ratio
            ratio = edge_load / self._edge_peak
            if ratio >= _HIGH_THRESHOLD:
                seg_congestion = "high"
            elif ratio >= _MEDIUM_THRESHOLD:
                seg_congestion = "medium"
            else:
                seg_congestion = "low"

            cfg = _LEVEL_CONFIG[seg_congestion]
            lat, lon = self._edge_lat_lon(edge_id)  # real coords from network

            # Resolve human-readable street name from the parsed network
            road_name = edge_id
            if self._network is not None:
                ei = self._network.edges.get(edge_id)
                if ei is not None and ei.name != edge_id:
                    road_name = ei.name

            incidents.append(
                TrafficIncident(
                    category="Jam",
                    severity=cfg["severity"],
                    description=(
                        f"Predicted {seg_congestion} congestion on {road_name} — "
                        f"load score {ratio:.0%} of network peak "
                        f"({edge_load} trips on segment, {trip_count} total in window)"
                    ),
                    from_location=road_name,
                    to_location="Dublin Network",
                    road=road_name,
                    length_meters=cfg["length_m"],
                    delay_seconds=round(cfg["delay_min"] * 60),
                    delay_minutes=cfg["delay_min"],
                    latitude=lat,
                    longitude=lon,
                )
            )
        return incidents


if __name__ == "__main__":
    predictor = TrafficPredictor()

    print(f"Loaded {sum(predictor._bins)} trips  |  peak bin: {predictor._peak} trips\n")
    print(f"{'Hour':<8} {'Congestion':<10} {'Trips':>6}  Bar")
    print("-" * 50)
    for h in range(24):
        slot_start = (h * 60) // _BIN_MINUTES
        hour_bins = predictor._bins[slot_start: slot_start + 4]
        avg_count = sum(hour_bins) / len(hour_bins) if hour_bins else 0
        congestion = predictor._congestion_level(int(avg_count))
        bar = "#" * int((avg_count / predictor._peak) * 30)
        print(f"  {h:02d}:00   {congestion:<10} {int(avg_count):>6}  {bar}")

    print("\nTop 5 busy segments at 08:30:")
    dt = datetime(2024, 1, 15, 8, 30, tzinfo=timezone.utc)
    for edge, count in predictor.top_edges_at(dt):
        print(f"  {edge:<30}  {count} trips")
