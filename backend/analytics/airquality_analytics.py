from typing import Dict, Any

from backend.models.airquality_models import AirQualityMetrics, PollutantLevels
from backend.models.bus_models import BusMetrics

# WHO / EU recommended limits for pollutants (μg/m³)
POLLUTANT_LIMITS = {
    "pm2_5": 25.0,
    "pm10": 50.0,
    "nitrogen_dioxide": 40.0,
    "carbon_monoxide": 10.0,  # mg/m³
    "ozone": 100.0,
    "sulphur_dioxide": 20.0,
}


def categorise_aqi(metrics: AirQualityMetrics) -> str:
    """
    Convert numeric AQI value to category.
    """
    aqi = metrics.aqi_value

    if aqi <= 50:
        return "low"
    elif aqi <= 100:
        return "medium"
    else:
        return "high"


def check_pollutant_safety(metrics: AirQualityMetrics) -> Dict[str, str]:
    """
    Check each pollutant against WHO/EU safe limits.
    Returns a dict mapping pollutant name to "safe" or "unsafe".
    """
    result = {}
    pollutants = metrics.pollutants
    if pollutants is None:
        return {}

    if not isinstance(pollutants, PollutantLevels):
        raise TypeError("metrics.pollutants must be PollutantLevels or None")

    result: Dict[str, str] = {}
    for pollutant, limit in POLLUTANT_LIMITS.items():
        value = getattr(pollutants, pollutant, 0.0)
        result[pollutant] = "unsafe" if value > limit else "safe"

    return result


def count_unsafe_pollutants(metrics: AirQualityMetrics) -> int:
    """
    Returns the number of pollutants that exceed safe limits.
    """
    safety_dict = check_pollutant_safety(metrics)
    return sum(1 for level in safety_dict.values() if level == "unsafe")


def overall_air_quality_level(metrics: AirQualityMetrics) -> str:
    """
    Combine AQI category and pollutant safety into a single overall level:
    - "low" if AQI is low and no pollutants unsafe
    - "medium" if AQI medium OR some unsafe pollutants
    - "high" if AQI high OR many unsafe pollutants
    """
    aqi_cat = categorise_aqi(metrics)
    unsafe_count = count_unsafe_pollutants(metrics)

    if aqi_cat == "low" and unsafe_count == 0:
        return "low"
    elif aqi_cat == "high" or unsafe_count >= 3:
        return "high"
    else:
        return "medium"


def build_wait_time_exposure(
    bus_metrics: BusMetrics,
    air_metrics: AirQualityMetrics,
    pollutant_key: str = "pm2_5",
    top_n: int = 10,
) -> Dict[str, Any]:
    """
    Build wait-time exposure metrics for bus stops using live air quality.
    Exposure = avg_wait_min * pollutant_value (or AQI if pollutant missing).
    """
    if bus_metrics is None or not bus_metrics.stop_avg_wait_min:
        return {
            "metric": None,
            "top": [],
            "stats": {"count": 0, "min": 0, "max": 0, "avg": 0},
            "by_stop": {},
        }

    pollutant_val = None
    unit = None
    metric_type = "aqi"

    if air_metrics and air_metrics.pollutants and hasattr(air_metrics.pollutants, pollutant_key):
        pollutant_val = getattr(air_metrics.pollutants, pollutant_key, None)
        units = getattr(air_metrics.pollutants, "units", {}) or {}
        unit = units.get(pollutant_key)
        metric_type = "pollutant"

    if pollutant_val is None:
        pollutant_val = getattr(air_metrics, "aqi_value", 0) if air_metrics else 0
        unit = unit or "AQI"
        metric_type = "aqi"

    by_stop: Dict[str, float] = {}
    for stop_id, avg_wait in bus_metrics.stop_avg_wait_min.items():
        if avg_wait is None:
            continue
        by_stop[stop_id] = round(float(pollutant_val) * float(avg_wait), 2)

    values = list(by_stop.values())
    if values:
        stats = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": round(sum(values) / len(values), 2),
        }
    else:
        stats = {"count": 0, "min": 0, "max": 0, "avg": 0}

    stop_names = {s.stop_id: s.name for s in bus_metrics.stops}
    ranked = sorted(by_stop.items(), key=lambda x: x[1], reverse=True)[: max(0, top_n)]
    top = [
        {
            "stop_id": stop_id,
            "name": stop_names.get(stop_id, stop_id),
            "avg_wait_min": bus_metrics.stop_avg_wait_min.get(stop_id),
            "exposure": exposure,
        }
        for stop_id, exposure in ranked
    ]

    metric = {
        "type": metric_type,
        "pollutant": pollutant_key if metric_type == "pollutant" else None,
        "value": pollutant_val,
        "unit": unit,
    }

    return {
        "metric": metric,
        "top": top,
        "stats": stats,
        "by_stop": by_stop,
    }
