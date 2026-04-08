import json
import csv
from datetime import datetime, timezone
from pathlib import Path

from backend.adapters.bus_adapter import BusAdapter
from backend.analytics.bus_analytics import (
    get_top_served_stops,
    get_wait_time_summary,
    get_wait_time_extremes,
    get_importance_scores,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_gtfs_root() -> Path:
    return _repo_root() / "data" / "historical"


def _metrics_output_path(gtfs_root: Path) -> Path:
    return gtfs_root / "GTFS" / "bus_metrics.json"


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def main() -> None:
    gtfs_root = _resolve_gtfs_root()
    adapter = BusAdapter(gtfs_path=gtfs_root)

    stops_file = adapter._resolve_stops_file()
    stop_times_file = adapter._resolve_stop_times_file()

    snapshot = adapter.fetch(location="dublin")
    metrics = snapshot.buses
    if metrics is None:
        raise RuntimeError("Bus metrics not available. Check GTFS files.")

    # Precompute arrivals per stop per hour bucket (0-23) for fast lookup at runtime.
    arrivals_by_hour = {}
    if stop_times_file.exists():
        dublin_stop_ids = {s.stop_id for s in metrics.stops}
        with stop_times_file.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                stop_id = row.get("stop_id")
                if stop_id not in dublin_stop_ids:
                    continue
                time_raw = row.get("arrival_time") or row.get("departure_time")
                arrival_sec = adapter._parse_gtfs_time_to_seconds(time_raw)
                if arrival_sec is None:
                    continue
                hour = int((arrival_sec // 3600) % 24)
                buckets = arrivals_by_hour.get(stop_id)
                if buckets is None:
                    buckets = [0] * 24
                    arrivals_by_hour[stop_id] = buckets
                buckets[hour] += 1

    # Compute analytics (mirrors SnapshotService._apply_analytics)
    metrics.top_served_stops = get_top_served_stops(metrics, top_n=10)
    summary, counts = get_wait_time_summary(metrics, top_n=15)
    metrics.wait_time_summary = summary
    metrics.wait_time_counts = counts
    best, worst = get_wait_time_extremes(metrics, n=15)
    metrics.wait_time_best = best
    metrics.wait_time_worst = worst
    scores, top_scores = get_importance_scores(metrics, weight_wait=0.6, weight_trips=0.4)
    metrics.stop_importance_scores = scores
    metrics.top_importance_stops = top_scores

    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stops_file": str(stops_file),
            "stop_times_file": str(stop_times_file),
            "stops_mtime": _safe_mtime(stops_file),
            "stop_times_mtime": _safe_mtime(stop_times_file),
        },
        "metrics": {
            "stops": [
                {
                    "stop_id": s.stop_id,
                    "name": s.name,
                    "lat": s.lat,
                    "lon": s.longitude,
                }
                for s in metrics.stops
            ],
            "stop_frequencies": metrics.stop_frequencies,
            "stop_arrivals_next_hour": metrics.stop_arrivals_next_hour,
            "stop_avg_wait_min": metrics.stop_avg_wait_min,
            "stop_importance_scores": metrics.stop_importance_scores,
            "arrivals_by_hour": arrivals_by_hour,
            "top_served_stops": metrics.top_served_stops,
            "wait_time_summary": metrics.wait_time_summary,
            "wait_time_counts": metrics.wait_time_counts,
            "wait_time_best": metrics.wait_time_best,
            "wait_time_worst": metrics.wait_time_worst,
            "top_importance_stops": metrics.top_importance_stops,
            "total_stops": metrics.total_stops,
            "total_routes": metrics.total_routes,
        },
    }

    out_path = _metrics_output_path(gtfs_root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    print(f"Saved bus metrics to {out_path}")


if __name__ == "__main__":
    main()
