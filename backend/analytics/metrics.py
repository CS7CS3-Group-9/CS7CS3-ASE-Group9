from __future__ import annotations

from typing import Optional

from models.airquality_models import AirQualityMetrics
from models.bike_models import BikeMetrics
from models.traffic_models import TrafficMetrics


EMISSIONS_G_PER_KM = {
    "car": 171.0,
    "bus": 82.0,
    "train": 41.0,
    "tram": 35.0,
    "metro": 41.0,
    "motorcycle": 103.0,
    "scooter": 0.0,
    "bike": 0.0,
    "walk": 0.0,
}


def estimate_emissions_kg(distance_km: float, mode: str = "car") -> float:
    """
    Estimate CO2e emissions for a trip in kilograms.
    """
    if distance_km < 0:
        raise ValueError("distance_km must be >= 0")

    factor = EMISSIONS_G_PER_KM.get(mode, EMISSIONS_G_PER_KM["car"])
    return (distance_km * factor) / 1000.0


def congestion_score(metrics: TrafficMetrics) -> float:
    """
    Convert TrafficMetrics into a 0-100 congestion score.
    """
    if metrics is None:
        return 0.0

    level_weight = {"low": 20.0, "medium": 50.0, "high": 80.0}
    base = level_weight.get(getattr(metrics, "congestion_level", "low"), 20.0)

    total_incidents = getattr(metrics, "total_incidents", 0) or 0
    avg_delay = getattr(metrics, "average_delay_minutes", 0) or 0

    score = base + min(total_incidents * 2.0, 20.0) + min(avg_delay, 20.0)
    return max(0.0, min(100.0, score))


def bike_availability_score(metrics: BikeMetrics) -> float:
    """
    Return bike availability as a percentage (0-100).
    """
    if metrics is None:
        return 0.0

    bikes = getattr(metrics, "available_bikes", 0) or 0
    docks = getattr(metrics, "available_docks", 0) or 0
    total = bikes + docks
    if total <= 0:
        return 0.0
    return round((bikes / total) * 100.0, 2)


def air_quality_score(metrics: AirQualityMetrics) -> float:
    """
    Convert AQI (lower is better) to a 0-100 score (higher is better).
    """
    if metrics is None:
        return 0.0

    aqi = getattr(metrics, "aqi_value", None)
    if aqi is None:
        return 0.0

    # Clamp AQI to 0..200 for scoring
    aqi = max(0.0, min(float(aqi), 200.0))
    score = 100.0 - (aqi / 2.0)
    return max(0.0, min(100.0, score))
