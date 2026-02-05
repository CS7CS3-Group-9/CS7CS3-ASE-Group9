import requests
from datetime import datetime

from backend.models.mobility_snapshot import MobilitySnapshot
from backend.adapters.base_adapter import DataAdapter
from backend.models.airquality_models import AirQualityMetrics

DUBLIN_AREAS = {
    # City Center / Inner City
    "city_center": {"lat": 53.3498, "lon": -6.2603},
    # South Side
    "south_side": {"lat": 53.3315, "lon": -6.2595},
    # North Side
    "north_side": {"lat": 53.3576, "lon": -6.2452},
    # West
    "west_dublin": {"lat": 53.3500, "lon": -6.3200},
    # East / Docklands
    "east_dublin": {"lat": 53.3454, "lon": -6.2290},
}


class AirQualityAdapter(DataAdapter):

    def source_name(self) -> str:
        return "airquality"

    def fetch(self, location: str = "city_center") -> MobilitySnapshot:

        #  Treat location as an area key; default safely
        area = location if location in DUBLIN_AREAS else "city_centre"
        coords = DUBLIN_AREAS[area]

        url = "https://air-quality-api.open-meteo.com/v1/air-quality"

        params = {"latitude": coords["lat"], "longitude": coords["lon"], "current": "european_aqi"}

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        european_aqi = data.get("current", {}).get("european_aqi", 0)

        airquality = AirQualityMetrics(area=area, european_aqi=float(european_aqi))

        return MobilitySnapshot(timestamp=datetime.utcnow(), location=location, airquality=airquality)
