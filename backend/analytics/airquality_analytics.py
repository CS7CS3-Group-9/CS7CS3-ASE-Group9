from typing import Dict

from backend.models.airquality_models import AirQualityMetrics, PollutantLevels

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
    assert isinstance(pollutants, PollutantLevels)
    if pollutants is None:
        return result

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
