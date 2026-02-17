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
