import requests
from datetime import datetime
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.adapters.base_adapter import DataAdapter
from backend.models.airquality_models import AirQualityMetrics

DUBLIN_AREAS = {
    # City Center / Inner City
    "city_center": {"lat": 53.3498, "lon": -6.2603, "radius_km": 0.5},
    "temple_bar": {"lat": 53.3441, "lon": -6.2660, "radius_km": 0.3},
    "grafton_street": {"lat": 53.3421, "lon": -6.2623, "radius_km": 0.4},
    # South Side
    "south_side": {"lat": 53.3315, "lon": -6.2595, "radius_km": 1.0},
    "ballsbridge": {"lat": 53.3303, "lon": -6.2318, "radius_km": 0.7},
    "ranelagh": {"lat": 53.3230, "lon": -6.2732, "radius_km": 0.6},
    "rathmines": {"lat": 53.3180, "lon": -6.2780, "radius_km": 0.8},
    "donnybrook": {"lat": 53.3261, "lon": -6.2240, "radius_km": 0.7},
    "sandymount": {"lat": 53.3245, "lon": -6.2050, "radius_km": 0.8},
    # North Side
    "north_side": {"lat": 53.3576, "lon": -6.2452, "radius_km": 1.0},
    "smithfield": {"lat": 53.3608, "lon": -6.2810, "radius_km": 0.5},
    "stoneybatter": {"lat": 53.3635, "lon": -6.2925, "radius_km": 0.5},
    "cabra": {"lat": 53.3675, "lon": -6.2935, "radius_km": 0.7},
    "phibsboro": {"lat": 53.3720, "lon": -6.2723, "radius_km": 0.7},
    # West
    "west_dublin": {"lat": 53.3500, "lon": -6.3200, "radius_km": 1.2},
    # East / Docklands
    "docklands": {"lat": 53.3454, "lon": -6.2290, "radius_km": 0.8},
    "ringsend": {"lat": 53.3380, "lon": -6.2160, "radius_km": 0.6},
}


class AirQualityAdapter(DataAdapter):

    def source_name(self) -> str:
        return "airquality"

    def fetch(self, location: str = "dublin") -> MobilitySnapshot:
        """
        Fetch air quality data and convert it into AirQualityMetrics.
        """
        # Example endpoint – replace with real one later
        url = "https://air-quality-api.open-meteo.com/v1/air-quality"

        params = {
            "latitude": DUBLIN_AREAS["city_center"]["lat"],
            "longitude": DUBLIN_AREAS["city_center"]["lon"],
            "current": ("european_aqi"),
        }

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Assume API returns a numeric AQI value
        aqi = data["current"]["aqi"].get("european_aqi", 0)

        airquality = AirQualityMetrics(aqi_value=aqi)

        return MobilitySnapshot(
            timestamp=datetime.utcnow(),
            location=location,
            airquality=airquality,
            source_status={self.source_name(): "live"},
        )
