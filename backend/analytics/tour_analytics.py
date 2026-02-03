from typing import List, Dict, Any, Optional, Tuple
import math


def get_tour_type_distribution(tours: List[Dict]) -> Dict[str, int]:
    """
    Returns distribution of tour types.

    Args:
        tours: List of tour dictionaries

    Returns:
        Dictionary with counts per tour type
    """
    distribution = {}

    for tour in tours:
        # Count by tour type
        tour_type = tour.get("type", "Unknown")
        distribution[tour_type] = distribution.get(tour_type, 0) + 1

    return distribution


def get_distance_statistics(tours: List[Dict]) -> Dict[str, Any]:
    """
    Calculate distance statistics for tours.

    Args:
        tours: List of tour dictionaries

    Returns:
        Dictionary with closest, farthest, and average distance
    """
    if not tours:
        return {"closest": None, "farthest": None, "average_distance": 0, "total_tours": 0}

    closest_tour = min(tours, key=lambda x: x.get("distance_km", float("inf")))
    farthest_tour = max(tours, key=lambda x: x.get("distance_km", 0))

    total_distance = sum(tour.get("distance_km", 0) for tour in tours)
    valid_distances = [t.get("distance_km", 0) for t in tours if t.get("distance_km") is not None]

    average_distance = sum(valid_distances) / len(valid_distances) if valid_distances else 0

    return {
        "closest": {
            "name": closest_tour.get("name", "Unknown"),
            "distance_km": closest_tour.get("distance_km", 0),
            "type": closest_tour.get("type", "Unknown"),
        },
        "farthest": {
            "name": farthest_tour.get("name", "Unknown"),
            "distance_km": farthest_tour.get("distance_km", 0),
            "type": farthest_tour.get("type", "Unknown"),
        },
        "average_distance": round(average_distance, 2),
        "total_tours": len(tours),
    }


def detect_tours_by_distance(
    tours: List[Dict],
    very_close_threshold: float = 2.5,
) -> List[Dict]:
    """
    Detect tours that are critically close or far from user location.

    Args:
        tours: List of tour dictionaries
        very_close_threshold: Distance in km for very close tours
        very_far_threshold: Distance in km for very far tours

    Returns:
        List of critical tours with level and details
    """
    walking_distance_tours = []
    distant_tours = []
    for tour in tours:
        distance = tour.get("distance_km")
        if distance is None:
            continue

        if distance <= very_close_threshold:
            walking_distance_tours.append(
                {
                    "tour": tour.get("name", "Unknown"),
                    "level": "walking_distance",
                    "distance": distance,
                    "type": tour.get("type", "Unknown"),
                }
            )
        elif distance > very_close_threshold:
            distant_tours.append(
                {
                    "tour": tour.get("name", "Unknown"),
                    "level": "distant",
                    "distance": distance,
                    "type": tour.get("type", "Unknown"),
                }
            )

    return walking_distance_tours, distant_tours


def get_tours_by_type(tours: List[Dict], tour_type: str) -> List[Dict]:
    """
    Filter tours by specific type

    Args:
        tours: List of tour dictionaries
        tour_type: Type to filter by (e.g., "Museum", "Free", "Paid")

    Returns:
        Filtered list of tours
    """
    if not tours:
        return []

    # Handle regular tour types
    return [tour for tour in tours if tour.get("type", "").lower() == tour_type.lower()]


def calculate_area_coverage(tours: List[Dict]) -> Dict[str, Any]:
    """
    Calculate the geographical area coverage of tours.

    Args:
        tours: List of tour dictionaries with latitude and longitude

    Returns:
        Dictionary with bounding box, center point, and radius
    """
    if not tours:
        return {
            "bounding_box": None,
            "center_point": {"latitude": 0, "longitude": 0},
            "radius_km": 0,
            "coverage_area_sqkm": 0,
        }

    # Extract valid coordinates
    coords = []
    for tour in tours:
        lat = tour.get("latitude")
        lon = tour.get("longitude")
        if lat is not None and lon is not None:
            coords.append((float(lat), float(lon)))

    if not coords:
        return {
            "bounding_box": None,
            "center_point": {"latitude": 0, "longitude": 0},
            "radius_km": 0,
            "coverage_area_sqkm": 0,
        }

    # Calculate bounding box
    lats = [coord[0] for coord in coords]
    lons = [coord[1] for coord in coords]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Calculate center point
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    # Calculate maximum radius from center
    max_radius = 0
    for lat, lon in coords:
        radius = calculate_distance(center_lat, center_lon, lat, lon)
        max_radius = max(max_radius, radius)

    # Approximate area (rectangle approximation)
    lat_span_km = calculate_distance(min_lat, min_lon, max_lat, min_lon)
    lon_span_km = calculate_distance(min_lat, min_lon, min_lat, max_lon)
    area_sqkm = lat_span_km * lon_span_km

    return {
        "bounding_box": {
            "min_latitude": min_lat,
            "max_latitude": max_lat,
            "min_longitude": min_lon,
            "max_longitude": max_lon,
        },
        "center_point": {"latitude": round(center_lat, 6), "longitude": round(center_lon, 6)},
        "radius_km": round(max_radius, 2),
        "coverage_area_sqkm": round(area_sqkm, 2),
    }


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance in km between two GPS coordinates.
    (Copied from your original script for consistency)
    """
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def generate_analytics_report(tours: List[Dict]) -> Dict[str, Any]:
    """
    Generate a comprehensive analytics report for tours.

    Args:
        tours: List of tour dictionaries

    Returns:
        Complete analytics report
    """
    return {
        "summary": {"total_tours": len(tours), "timestamp": "2024-01-01T00:00:00Z"},  # You can add datetime.now() here
        "type_distribution": get_tour_type_distribution(tours),
        "distance_statistics": get_distance_statistics(tours),
    }


def print_analytics_report(report: Dict[str, Any]):
    """
    Print analytics report in a readable format.

    Args:
        report: Analytics report dictionary
    """
    print("\n" + "=" * 60)
    print("TOUR ANALYTICS REPORT")
    print("=" * 60)

    print(f"\n📊 SUMMARY")
    print(f"   Total Tours: {report['summary']['total_tours']}")

    print(f"\n🎯 DISTANCE STATISTICS")
    stats = report["distance_statistics"]
    if stats["closest"]:
        print(f"   Closest: {stats['closest']['name']} ({stats['closest']['distance_km']} km)")
        print(f"   Farthest: {stats['farthest']['name']} ({stats['farthest']['distance_km']} km)")
        print(f"   Average Distance: {stats['average_distance']} km")

    print(f"\n🏷️  TYPE DISTRIBUTION")
    for tour_type, count in report["type_distribution"].items():
        print(f"   {tour_type}: {count}")


# Example usage in your main script
if __name__ == "__main__":
    # This would be integrated with your existing main() function
    print("Tour Analytics Module")

    # Example test with sample data
    from typing import List, Dict

    sample_tours: List[Dict] = [
        {
            "name": "Test Museum",
            "type": "Museum",
            "latitude": 53.3498,
            "longitude": -6.2603,
            "distance_km": 0.5,
        }
    ]

    report = generate_analytics_report(sample_tours)
    print_analytics_report(report)
