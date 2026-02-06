import requests
from datetime import datetime

from backend.adapters.base_adapter import DataAdapter
from backend.models.mobility_snapshot import MobilitySnapshot
from backend.models.tour_models import Attraction, AttractionMetrics


class TourAdapter(DataAdapter):
    """
    Adapter for OpenStreetMap Overpass tourism / attraction data.
    Returns partial MobilitySnapshot with tours=AttractionMetrics.
    """

    def source_name(self) -> str:
        return "tours"

    def fetch(self, location: str = "dublin", radius_km: float = 5) -> MobilitySnapshot:
        """
        Fetch tourism / attraction data and convert it into AttractionMetrics.
        In unit tests, requests.post is mocked.
        """

        url = "https://overpass-api.de/api/interpreter"

        # Fixed Dublin centre for now (geocoding can be added later)
        lat, lon = 53.3498, -6.2603
        radius_m = int(radius_km * 1000)

        overpass_query = (
            f"[out:json];("
            f'node["tourism"="attraction"](around:{radius_m},{lat},{lon});'
            f'node["tourism"="museum"](around:{radius_m},{lat},{lon});'
            f'node["historic"="castle"](around:{radius_m},{lat},{lon});'
            f'node["historic"="monument"](around:{radius_m},{lat},{lon});'
            f'way["tourism"="attraction"](around:{radius_m},{lat},{lon});'
            f'way["tourism"="museum"](around:{radius_m},{lat},{lon});'
            f'way["historic"="castle"](around:{radius_m},{lat},{lon});'
            f'way["leisure"="park"](around:{radius_m},{lat},{lon});'
            f");out center;"
        )

        response = requests.post(url, data=overpass_query, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Will raise KeyError if malformed (test expects this)
        elements = data["elements"]

        attractions = []
        attractions_by_type = {}

        wheelchair_yes_count = 0

        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name", "Unknown")

            # Coordinates
            if "lat" in element and "lon" in element:
                latitude = element["lat"]
                longitude = element["lon"]
            elif "center" in element:
                latitude = element["center"].get("lat")
                longitude = element["center"].get("lon")
            else:
                continue

            if latitude is None or longitude is None:
                continue

            # Determine attraction type with sensible precedence
            tourism = tags.get("tourism")
            historic = tags.get("historic")
            leisure = tags.get("leisure")

            if tourism and tourism != "attraction":
                # tourism already specific: museum, hotel, information, etc.
                attraction_type = tourism
            else:
                # tourism is generic (or missing): prefer historic/leisure if present
                attraction_type = historic or leisure or tourism or "unknown"

            open_times = tags.get("opening_hours")
            phone = tags.get("phone")
            website = tags.get("website")
            wheelchair = tags.get("wheelchair")

            attractions_by_type[attraction_type] = attractions_by_type.get(attraction_type, 0) + 1

            if wheelchair == "yes":
                wheelchair_yes_count += 1

            attractions.append(
                Attraction(
                    attraction_id=element.get("id"),
                    attraction_name=name,
                    attraction_type=attraction_type,
                    latitude=latitude,
                    longitude=longitude,
                    open_times=open_times,
                    website=website,
                    phone=phone,
                    wheelchair_accessible=wheelchair,
                    tags=tags,
                )
            )

        metrics = AttractionMetrics(
            total_attractions=len(attractions),
            attractions_by_type=attractions_by_type,
            wheelchair_accessible_count=wheelchair_yes_count,
            attractions=attractions,
        )

        return MobilitySnapshot(timestamp=datetime.utcnow(), location=location, tours=metrics)
