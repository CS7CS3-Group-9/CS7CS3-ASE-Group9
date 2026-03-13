from typing import List, Dict, Any, Optional, Tuple
import math

from backend.models.bus_models import BusStop, BusMetrics


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two GPS coordinates."""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


# ========== Stop‑only analytics (no population) ==========


def get_stop_frequencies(metrics: BusMetrics) -> Dict[str, int]:
    """Returns the frequency (number of trips) for each stop."""
    return metrics.stop_frequencies


def get_top_served_stops(metrics: BusMetrics, top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Return top N stops by stop_times frequency (proxy for buses serving stop).
    """
    if not metrics.stops:
        return []
    stop_names = {s.stop_id: s.name for s in metrics.stops}
    counts = metrics.stop_frequencies or {}
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top = ranked[: max(0, top_n)]
    return [{"stop_id": stop_id, "name": stop_names.get(stop_id, stop_id), "buses": count} for stop_id, count in top]


def _wait_category(avg_wait_min: float) -> str:
    if avg_wait_min < 8:
        return "good"
    if avg_wait_min <= 23:
        return "ok"
    return "poor"


def get_wait_time_summary(metrics: BusMetrics, top_n: int = 10) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Return top N worst stops by average wait time and counts by category.
    """
    if not metrics.stop_avg_wait_min:
        return [], {"good": 0, "ok": 0, "poor": 0}

    stop_names = {s.stop_id: s.name for s in metrics.stops}
    ranked = sorted(metrics.stop_avg_wait_min.items(), key=lambda x: x[1], reverse=True)
    top = ranked[: max(0, top_n)]
    summary = []
    counts = {"good": 0, "ok": 0, "poor": 0}
    for stop_id, avg_min in metrics.stop_avg_wait_min.items():
        counts[_wait_category(avg_min)] += 1
    for stop_id, avg_min in top:
        summary.append(
            {
                "stop_id": stop_id,
                "name": stop_names.get(stop_id, stop_id),
                "avg_wait_min": avg_min,
                "category": _wait_category(avg_min),
            }
        )
    return summary, counts


def get_wait_time_extremes(metrics: BusMetrics, n: int = 5) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Return (best, worst) lists by average wait time.
    Best = lowest waits, Worst = highest waits.
    """
    if not metrics.stop_avg_wait_min:
        return [], []

    stop_names = {s.stop_id: s.name for s in metrics.stops}
    ranked = sorted(metrics.stop_avg_wait_min.items(), key=lambda x: x[1])
    best_raw = ranked[: max(0, n)]
    worst_raw = list(reversed(ranked))[: max(0, n)]

    def _pack(items):
        return [
            {
                "stop_id": stop_id,
                "name": stop_names.get(stop_id, stop_id),
                "avg_wait_min": avg_min,
                "category": _wait_category(avg_min),
            }
            for stop_id, avg_min in items
        ]

    return _pack(best_raw), _pack(worst_raw)


def get_importance_scores(
    metrics: BusMetrics, weight_wait: float = 0.6, weight_trips: float = 0.4
) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """
    Compute importance score per stop using:
      score = weight_wait * (1 - normalized_wait) + weight_trips * normalized_trips
    Lower wait = better, higher trips = better.
    """
    waits = metrics.stop_avg_wait_min or {}
    trips = metrics.stop_frequencies or {}
    if not waits or not trips:
        return {}, []

    # Normalize waits and trips to [0,1]
    wait_vals = list(waits.values())
    trip_vals = list(trips.values())
    min_wait, max_wait = min(wait_vals), max(wait_vals)
    min_trip, max_trip = min(trip_vals), max(trip_vals)

    def _norm(v, vmin, vmax):
        if vmax <= vmin:
            return 0.0
        return (v - vmin) / (vmax - vmin)

    scores: Dict[str, float] = {}
    stop_names = {s.stop_id: s.name for s in metrics.stops}
    for stop_id, trip_count in trips.items():
        if stop_id not in waits:
            continue
        wait = waits[stop_id]
        n_wait = _norm(wait, min_wait, max_wait)
        n_trip = _norm(trip_count, min_trip, max_trip)
        score = weight_wait * (1.0 - n_wait) + weight_trips * n_trip
        scores[stop_id] = round(score, 3)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    top = [
        {
            "stop_id": stop_id,
            "name": stop_names.get(stop_id, stop_id),
            "score": score,
            "avg_wait_min": waits.get(stop_id),
            "trip_count": trips.get(stop_id),
        }
        for stop_id, score in ranked
    ]
    return scores, top


def compute_average_waits_from_stop_times(stop_times_file, dublin_stop_ids, parse_time_fn) -> Dict[str, float]:
    """
    Compute average wait time between buses for each stop (in minutes),
    based on arrival_time/departure_time in stop_times.txt.
    """
    if not stop_times_file.exists():
        return {}

    times_by_stop: Dict[str, list[int]] = {}
    line_count = 0
    with open(stop_times_file, "r", encoding="utf-8") as f:
        import csv

        reader = csv.DictReader(f)
        for row in reader:
            line_count += 1
            stop_id = row.get("stop_id")
            if stop_id not in dublin_stop_ids:
                continue
            time_raw = row.get("arrival_time") or row.get("departure_time")
            t = parse_time_fn(time_raw)
            if t is None:
                continue
            times_by_stop.setdefault(stop_id, []).append(t)

    avg_waits: Dict[str, float] = {}
    for stop_id, times in times_by_stop.items():
        if len(times) < 2:
            continue
        times.sort()
        deltas = [b - a for a, b in zip(times, times[1:]) if b > a]
        if not deltas:
            continue
        avg_waits[stop_id] = round(sum(deltas) / len(deltas) / 60.0, 1)

    return avg_waits


def detect_low_frequency_stops(metrics: BusMetrics, threshold: int = 10) -> List[Dict[str, Any]]:
    """Detect stops with frequency below the threshold."""
    low_freq = []
    for stop in metrics.stops:
        freq = metrics.stop_frequencies.get(stop.stop_id, 0)
        if freq < threshold:
            low_freq.append({"stop_id": stop.stop_id, "name": stop.name, "frequency": freq, "level": "low"})
    return low_freq


def detect_high_frequency_stops(metrics: BusMetrics, threshold: int = 100) -> List[Dict[str, Any]]:
    """Detect stops with frequency above the threshold."""
    high_freq = []
    for stop in metrics.stops:
        freq = metrics.stop_frequencies.get(stop.stop_id, 0)
        if freq > threshold:
            high_freq.append({"stop_id": stop.stop_id, "name": stop.name, "frequency": freq, "level": "high"})
    return high_freq


def get_stop_spread(metrics: BusMetrics) -> Dict[str, Any]:
    """
    Calculate geographical spread of stops.
    Returns bounding box, center point, and average distance from center.
    """
    if not metrics.stops:
        return {
            "bounding_box": None,
            "center_point": {"lat": 0, "lon": 0},
            "average_distance_from_center": 0,
            "total_stops": 0,
        }

    lats = [s.lat for s in metrics.stops]
    lons = [s.longitude for s in metrics.stops]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    distances = [calculate_distance(center_lat, center_lon, s.lat, s.longitude) for s in metrics.stops]
    avg_dist = sum(distances) / len(distances)

    return {
        "bounding_box": {
            "min_lat": round(min_lat, 6),
            "max_lat": round(max_lat, 6),
            "min_lon": round(min_lon, 6),
            "max_lon": round(max_lon, 6),
        },
        "center_point": {"lat": round(center_lat, 6), "lon": round(center_lon, 6)},
        "average_distance_from_center": round(avg_dist, 2),
        "total_stops": len(metrics.stops),
    }


def get_isolated_stops(metrics: BusMetrics, distance_threshold: float = 2.0) -> List[Dict[str, Any]]:  # km
    """
    Identify stops that are isolated: distance to nearest other stop > threshold.
    """
    if len(metrics.stops) < 2:
        return []

    isolated = []
    for i, stop in enumerate(metrics.stops):
        min_dist = float("inf")
        for j, other in enumerate(metrics.stops):
            if i == j:
                continue
            dist = calculate_distance(stop.lat, stop.longitude, other.lat, other.longitude)
            if dist < min_dist:
                min_dist = dist
        if min_dist > distance_threshold:
            isolated.append(
                {
                    "stop_id": stop.stop_id,
                    "name": stop.name,
                    "distance_to_nearest": round(min_dist, 2),
                    "threshold": distance_threshold,
                }
            )
    return isolated


def get_frequency_statistics(metrics: BusMetrics) -> Dict[str, Any]:
    """
    Overall frequency statistics: min, max, average, total trips.
    """
    if not metrics.stop_frequencies:
        return {"min_frequency": 0, "max_frequency": 0, "average_frequency": 0, "total_trips": 0, "stops_with_data": 0}

    freqs = list(metrics.stop_frequencies.values())
    total_trips = sum(freqs)
    stops_with_data = len(freqs)
    min_freq = min(freqs)
    max_freq = max(freqs)
    avg_freq = total_trips / stops_with_data if stops_with_data else 0

    return {
        "min_frequency": min_freq,
        "max_frequency": max_freq,
        "average_frequency": round(avg_freq, 1),
        "total_trips": total_trips,
        "stops_with_data": stops_with_data,
    }


# ========== Population‑aware analytics ==========


def find_nearest_stop_distance(pop_lat: float, pop_lon: float, stops: List[BusStop]) -> Tuple[Optional[BusStop], float]:
    """
    Find the nearest bus stop to a population point.
    Returns (stop, distance_km) or (None, infinity) if no stops.
    """
    if not stops:
        return None, float("inf")

    min_dist = float("inf")
    nearest = None
    for stop in stops:
        dist = calculate_distance(pop_lat, pop_lon, stop.lat, stop.longitude)
        if dist < min_dist:
            min_dist = dist
            nearest = stop
    return nearest, min_dist


def get_population_coverage_metrics(population: List[Dict[str, Any]], stops: List[BusStop]) -> Dict[str, Any]:
    """
    For each population centre, compute distance to nearest stop.
    Returns summary statistics and per‑point distances.
    """
    if not population or not stops:
        return {
            "total_population_centres": len(population),
            "average_distance": 0,
            "min_distance": 0,
            "max_distance": 0,
            "centres_within_1km": 0,
            "centres_within_2km": 0,
            "centres_beyond_2km": 0,
            "details": [],
        }

    distances = []
    details = []
    for pop in population:
        nearest_stop, dist = find_nearest_stop_distance(pop["lat"], pop["lon"], stops)
        distances.append(dist)
        details.append(
            {
                "name": pop.get("name", "Unknown"),
                "population": pop.get("pop", 0),
                "lat": pop["lat"],
                "lon": pop["lon"],
                "distance_to_nearest_stop_km": round(dist, 2),
                "nearest_stop_id": nearest_stop.stop_id if nearest_stop else None,
                "nearest_stop_name": nearest_stop.name if nearest_stop else None,
            }
        )

    within_1km = sum(1 for d in distances if d <= 1.0)
    within_2km = sum(1 for d in distances if 1.0 < d <= 2.0)
    beyond_2km = sum(1 for d in distances if d > 2.0)

    return {
        "total_population_centres": len(population),
        "average_distance": round(sum(distances) / len(distances), 2),
        "min_distance": round(min(distances), 2),
        "max_distance": round(max(distances), 2),
        "centres_within_1km": within_1km,
        "centres_within_2km": within_2km,
        "centres_beyond_2km": beyond_2km,
        "details": details,
    }


def identify_underserved_populations(
    population: List[Dict[str, Any]], stops: List[BusStop], threshold_km: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Return population centres whose nearest stop is farther than threshold_km.
    """
    underserved = []
    for pop in population:
        _, dist = find_nearest_stop_distance(pop["lat"], pop["lon"], stops)
        if dist > threshold_km:
            underserved.append(
                {
                    "name": pop.get("name", "Unknown"),
                    "population": pop.get("pop", 0),
                    "lat": pop["lat"],
                    "lon": pop["lon"],
                    "distance_to_nearest_stop_km": round(dist, 2),
                }
            )
    return underserved


def get_stop_density_around_population(
    population: List[Dict[str, Any]], stops: List[BusStop], radius_km: float = 1.0
) -> List[Dict[str, Any]]:
    """
    For each population centre, count how many stops are within radius_km.
    """
    result = []
    for pop in population:
        count = 0
        for stop in stops:
            dist = calculate_distance(pop["lat"], pop["lon"], stop.lat, stop.longitude)
            if dist <= radius_km:
                count += 1
        result.append(
            {
                "name": pop.get("name", "Unknown"),
                "population": pop.get("pop", 0),
                "lat": pop["lat"],
                "lon": pop["lon"],
                f"stops_within_{radius_km}km": count,
            }
        )
    return result
