from typing import List, Dict, Any

from backend.models.bike_models import StationMetrics


def get_station_occupancy(
    stations: List[StationMetrics],
) -> Dict[str, float]:
    """
    Returns occupancy percentage per station.
    """

    occupancy: Dict[str, float] = {}
    for station in stations:
        if station.total_spaces <= 0:
            continue

        occupancy[station.name] = round((station.free_bikes / station.total_spaces) * 100, 1)

    return occupancy


def detect_critical_occupancy(
    stations: List[StationMetrics],
    low_threshold: float = 10,
    high_threshold: float = 90,
) -> List[Dict[str, Any]]:
    """
    Detect stations with critically low or high occupancy.
    """

    critical: List[Dict[str, Any]] = []
    for station in stations:
        if station.total_spaces <= 0:
            continue

        occupancy = (station.free_bikes / station.total_spaces) * 100

        if occupancy < low_threshold:
            critical.append(
                {
                    "station": station.name,
                    "level": "low",
                    "value": round(occupancy, 1),
                }
            )
        elif occupancy > high_threshold:
            critical.append(
                {
                    "station": station.name,
                    "level": "high",
                    "value": round(occupancy, 1),
                }
            )

    return critical
